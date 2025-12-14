import pytest
import ast
import asyncio
import subprocess
import shlex

def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".md" and "README" in file_path.name:
        return ReadmeFile.from_parent(parent, path=file_path)

class ReadmeFile(pytest.File):
    def collect(self):
        raw_text = self.path.read_text(encoding="utf-8")
        lines = raw_text.splitlines()
        
        in_block = False
        block_type = None  # 'python' or 'bash'
        code_lines = []
        start_line = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Detect Start
            if stripped.startswith("```") and not in_block:
                if "python" in stripped or "py" in stripped:
                    block_type = "python"
                    in_block = True
                elif "bash" in stripped or "sh" in stripped or "shell" in stripped:
                    block_type = "bash"
                    in_block = True
                
                if in_block:
                    start_line = i + 1
                    code_lines = []
                continue
            
            # Detect End
            if stripped == "```" and in_block:
                in_block = False
                if code_lines:
                    code_snippet = "\n".join(code_lines)
                    yield ReadmeItem.from_parent(
                        self, 
                        name=f"line_{start_line}", 
                        spec=code_snippet,
                        block_type=block_type
                    )
                continue
            
            if in_block:
                code_lines.append(line)

class ReadmeItem(pytest.Item):
    def __init__(self, name, parent, spec, block_type):
        super().__init__(name, parent)
        self.spec = spec
        self.block_type = block_type

    def runtest(self):
        if self.block_type == "python":
            self.run_python()
        elif self.block_type == "bash":
            self.run_bash()

    def run_python(self):
        # (Same Python Logic as before...)
        try:
            ast.parse(self.spec)
        except SyntaxError as e:
            raise ReadmeSyntaxError(f"Syntax Error: {e}")

        local_scope = {}
        # Simple Async Wrapper check
        if "await " in self.spec:
            wrapped_code = f"async def _test_wrapper():\n" + "\n".join(
                [f"    {line}" for line in self.spec.splitlines()]
            )
            exec(wrapped_code, {}, local_scope)
            asyncio.run(local_scope["_test_wrapper"]())
        else:
            exec(self.spec, {"__name__": "__main__"})

    def run_bash(self):
        # DANGEROUS: Executes shell commands
        # We split multi-line bash scripts and run them one by one
        commands = self.spec.splitlines()
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd or cmd.startswith("#"):
                continue # Skip comments/empty lines
            
            # Run the command
            # check=True will raise an error if the command fails (returns non-zero)
            subprocess.run(cmd, shell=True, check=True, executable="/bin/bash")

    def repr_failure(self, excinfo):
        return f"README {self.block_type.upper()} Block failed at {self.name}: {excinfo.value}"

    def reportinfo(self):
        return self.path, 0, f"README block: {self.name}"

class ReadmeSyntaxError(Exception):
    pass