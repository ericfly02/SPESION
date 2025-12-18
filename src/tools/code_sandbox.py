"""Code Sandbox - Ejecución segura de código con Docker."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Timeout por defecto para ejecución de código (segundos)
DEFAULT_TIMEOUT = 30

# Imagen Docker para sandbox (debe construirse con Dockerfile.sandbox)
SANDBOX_IMAGE = "spesion-sandbox:latest"


@tool
def execute_python_code(
    code: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Ejecuta código Python de forma segura en un sandbox Docker.
    
    Args:
        code: Código Python a ejecutar
        timeout: Timeout en segundos (max 60)
        
    Returns:
        Dict con stdout, stderr y status
    """
    timeout = min(timeout, 60)  # Max 60 segundos
    
    # Verificar si Docker está disponible
    if not _docker_available():
        # Fallback a ejecución local restringida
        return _execute_python_local(code, timeout)
    
    try:
        # Crear archivo temporal con el código
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(code)
            code_file = Path(f.name)
        
        # Ejecutar en Docker
        result = subprocess.run(
            [
                "docker", "run",
                "--rm",
                "--network", "none",  # Sin red
                "--memory", "256m",   # Limitar memoria
                "--cpus", "0.5",      # Limitar CPU
                "-v", f"{code_file}:/code/script.py:ro",
                SANDBOX_IMAGE,
                "python", "/code/script.py",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        # Limpiar archivo temporal
        code_file.unlink(missing_ok=True)
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:5000],  # Limitar output
            "stderr": result.stderr[:2000],
            "return_code": result.returncode,
            "execution_method": "docker",
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Timeout: ejecución excedió {timeout} segundos",
            "stdout": "",
            "stderr": "",
        }
    except Exception as e:
        logger.error(f"Error ejecutando código en Docker: {e}")
        return _execute_python_local(code, timeout)


def _execute_python_local(
    code: str,
    timeout: int,
) -> dict[str, Any]:
    """Ejecuta código Python localmente (fallback).
    
    Usa restricciones básicas pero NO es un sandbox seguro.
    Solo para desarrollo/testing.
    """
    logger.warning("Ejecutando código SIN sandbox Docker (solo para desarrollo)")
    
    # Verificar código peligroso básico
    dangerous_patterns = [
        "import os",
        "import subprocess",
        "import sys",
        "__import__",
        "eval(",
        "exec(",
        "open(",
        "file(",
        "input(",
    ]
    
    for pattern in dangerous_patterns:
        if pattern in code:
            return {
                "success": False,
                "error": f"Código contiene patrón no permitido: {pattern}",
                "stdout": "",
                "stderr": "",
                "execution_method": "local_blocked",
            }
    
    try:
        # Crear namespace restringido
        restricted_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sorted": sorted,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "True": True,
                "False": False,
                "None": None,
            }
        }
        
        # Capturar stdout
        import io
        import contextlib
        
        stdout_capture = io.StringIO()
        
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, restricted_globals)
        
        return {
            "success": True,
            "stdout": stdout_capture.getvalue()[:5000],
            "stderr": "",
            "return_code": 0,
            "execution_method": "local_restricted",
            "warning": "Ejecutado sin sandbox Docker - usar solo para desarrollo",
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
            "execution_method": "local_restricted",
        }


def _docker_available() -> bool:
    """Verifica si Docker está disponible."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


@tool
def execute_shell_command(
    command: str,
    timeout: int = 10,
) -> dict[str, Any]:
    """Ejecuta un comando shell de forma segura (solo comandos permitidos).
    
    Comandos permitidos: ls, cat, head, tail, wc, grep, find, echo
    
    Args:
        command: Comando a ejecutar
        timeout: Timeout en segundos
        
    Returns:
        Dict con resultado
    """
    # Lista blanca de comandos
    allowed_commands = {"ls", "cat", "head", "tail", "wc", "grep", "find", "echo", "pwd"}
    
    # Extraer comando base
    parts = command.strip().split()
    if not parts:
        return {"success": False, "error": "Comando vacío"}
    
    base_command = parts[0]
    
    if base_command not in allowed_commands:
        return {
            "success": False,
            "error": f"Comando no permitido: {base_command}. Permitidos: {', '.join(allowed_commands)}",
        }
    
    # Verificar patrones peligrosos
    dangerous = ["|", ";", "&&", "||", ">", "<", "`", "$", ".."]
    for d in dangerous:
        if d in command:
            return {
                "success": False,
                "error": f"Patrón no permitido en comando: {d}",
            }
    
    try:
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",  # Directorio seguro
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:1000],
            "return_code": result.returncode,
        }
        
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout después de {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def analyze_code(
    code: str,
    language: str = "python",
) -> dict[str, Any]:
    """Analiza código sin ejecutarlo.
    
    Proporciona información sobre:
    - Imports utilizados
    - Funciones definidas
    - Clases definidas
    - Posibles issues
    
    Args:
        code: Código a analizar
        language: Lenguaje del código
        
    Returns:
        Dict con análisis
    """
    if language != "python":
        return {"error": f"Análisis de {language} no soportado aún"}
    
    try:
        import ast
        
        tree = ast.parse(code)
        
        imports = []
        functions = []
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
            elif isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "has_docstring": ast.get_docstring(node) is not None,
                    "line": node.lineno,
                })
            elif isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in node.body 
                    if isinstance(n, ast.FunctionDef)
                ]
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "line": node.lineno,
                })
        
        # Detectar posibles issues
        issues = []
        
        # Imports peligrosos
        dangerous_imports = {"os", "subprocess", "sys", "shutil"}
        for imp in imports:
            if imp.split(".")[0] in dangerous_imports:
                issues.append(f"Import potencialmente peligroso: {imp}")
        
        # Funciones sin docstring
        for func in functions:
            if not func["has_docstring"] and not func["name"].startswith("_"):
                issues.append(f"Función '{func['name']}' sin docstring")
        
        return {
            "success": True,
            "imports": imports,
            "functions": functions,
            "classes": classes,
            "issues": issues,
            "lines_of_code": len(code.splitlines()),
        }
        
    except SyntaxError as e:
        return {
            "success": False,
            "error": f"Error de sintaxis: {e}",
            "line": e.lineno,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_sandbox_tools() -> list:
    """Crea las herramientas de sandbox.
    
    Returns:
        Lista de herramientas
    """
    return [
        execute_python_code,
        execute_shell_command,
        analyze_code,
    ]

