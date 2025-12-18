"""GitHub MCP - Integración con GitHub API."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_github_client():
    """Obtiene el cliente de GitHub."""
    try:
        from github import Github
        from src.core.config import settings
        
        if not settings.github.token:
            logger.warning("Token de GitHub no configurado")
            return None
        
        return Github(settings.github.token.get_secret_value())
        
    except ImportError:
        logger.error("PyGithub no instalado. pip install PyGithub")
        return None


@tool
def get_repo_info(repo_name: str) -> dict[str, Any]:
    """Obtiene información de un repositorio.
    
    Args:
        repo_name: Nombre del repo en formato 'owner/repo'
        
    Returns:
        Dict con información del repositorio
    """
    client = _get_github_client()
    if client is None:
        return {"error": "GitHub no disponible"}
    
    try:
        repo = client.get_repo(repo_name)
        
        return {
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "language": repo.language,
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "open_issues": repo.open_issues_count,
            "default_branch": repo.default_branch,
            "last_push": repo.pushed_at.isoformat() if repo.pushed_at else None,
            "url": repo.html_url,
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo repo {repo_name}: {e}")
        return {"error": str(e)}


@tool
def get_file_content(
    repo_name: str,
    file_path: str,
    branch: str | None = None,
) -> dict[str, Any]:
    """Obtiene el contenido de un archivo de un repositorio.
    
    Args:
        repo_name: Nombre del repo en formato 'owner/repo'
        file_path: Ruta del archivo en el repo
        branch: Branch (default: default branch)
        
    Returns:
        Dict con contenido del archivo
    """
    client = _get_github_client()
    if client is None:
        return {"error": "GitHub no disponible"}
    
    try:
        repo = client.get_repo(repo_name)
        ref = branch or repo.default_branch
        
        file_content = repo.get_contents(file_path, ref=ref)
        
        if isinstance(file_content, list):
            return {"error": "La ruta es un directorio, no un archivo"}
        
        # Decodificar contenido
        content = file_content.decoded_content.decode("utf-8")
        
        return {
            "path": file_path,
            "name": file_content.name,
            "size": file_content.size,
            "sha": file_content.sha,
            "content": content[:10000],  # Limitar a 10k chars
            "truncated": len(content) > 10000,
            "url": file_content.html_url,
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo archivo {file_path}: {e}")
        return {"error": str(e)}


@tool
def list_pull_requests(
    repo_name: str,
    state: str = "open",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Lista pull requests de un repositorio.
    
    Args:
        repo_name: Nombre del repo en formato 'owner/repo'
        state: Estado de los PRs ('open', 'closed', 'all')
        limit: Número máximo de PRs a listar
        
    Returns:
        Lista de PRs
    """
    client = _get_github_client()
    if client is None:
        return [{"error": "GitHub no disponible"}]
    
    try:
        repo = client.get_repo(repo_name)
        prs = repo.get_pulls(state=state, sort="updated", direction="desc")
        
        results = []
        for pr in prs[:limit]:
            results.append({
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "author": pr.user.login,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "url": pr.html_url,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
                "mergeable": pr.mergeable,
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error listando PRs de {repo_name}: {e}")
        return [{"error": str(e)}]


@tool
def get_pr_diff(
    repo_name: str,
    pr_number: int,
) -> dict[str, Any]:
    """Obtiene el diff de un pull request.
    
    Args:
        repo_name: Nombre del repo en formato 'owner/repo'
        pr_number: Número del PR
        
    Returns:
        Dict con archivos cambiados y diff
    """
    client = _get_github_client()
    if client is None:
        return {"error": "GitHub no disponible"}
    
    try:
        repo = client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        files = []
        for file in pr.get_files():
            files.append({
                "filename": file.filename,
                "status": file.status,  # added, removed, modified
                "additions": file.additions,
                "deletions": file.deletions,
                "patch": file.patch[:5000] if file.patch else None,  # Limitar
            })
        
        return {
            "pr_number": pr_number,
            "title": pr.title,
            "description": pr.body[:1000] if pr.body else None,
            "total_additions": pr.additions,
            "total_deletions": pr.deletions,
            "files": files[:20],  # Limitar a 20 archivos
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo diff de PR #{pr_number}: {e}")
        return {"error": str(e)}


@tool
def list_issues(
    repo_name: str,
    state: str = "open",
    labels: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Lista issues de un repositorio.
    
    Args:
        repo_name: Nombre del repo en formato 'owner/repo'
        state: Estado ('open', 'closed', 'all')
        labels: Filtrar por labels
        limit: Número máximo
        
    Returns:
        Lista de issues
    """
    client = _get_github_client()
    if client is None:
        return [{"error": "GitHub no disponible"}]
    
    try:
        repo = client.get_repo(repo_name)
        
        kwargs = {"state": state, "sort": "updated", "direction": "desc"}
        if labels:
            kwargs["labels"] = labels
        
        issues = repo.get_issues(**kwargs)
        
        results = []
        for issue in issues[:limit]:
            # Filtrar PRs (la API incluye PRs como issues)
            if issue.pull_request:
                continue
            
            results.append({
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "author": issue.user.login,
                "created_at": issue.created_at.isoformat(),
                "labels": [l.name for l in issue.labels],
                "comments": issue.comments,
                "url": issue.html_url,
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error listando issues de {repo_name}: {e}")
        return [{"error": str(e)}]


@tool
def search_code(
    query: str,
    repo_name: str | None = None,
    language: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Busca código en GitHub.
    
    Args:
        query: Términos de búsqueda
        repo_name: Limitar a un repo específico (opcional)
        language: Filtrar por lenguaje
        limit: Número máximo de resultados
        
    Returns:
        Lista de resultados de búsqueda
    """
    client = _get_github_client()
    if client is None:
        return [{"error": "GitHub no disponible"}]
    
    try:
        # Construir query
        search_query = query
        if repo_name:
            search_query += f" repo:{repo_name}"
        if language:
            search_query += f" language:{language}"
        
        results = client.search_code(search_query)
        
        items = []
        for item in results[:limit]:
            items.append({
                "name": item.name,
                "path": item.path,
                "repo": item.repository.full_name,
                "url": item.html_url,
                "sha": item.sha,
            })
        
        return items
        
    except Exception as e:
        logger.error(f"Error buscando código: {e}")
        return [{"error": str(e)}]


def create_github_tools() -> list:
    """Crea las herramientas de GitHub.
    
    Returns:
        Lista de herramientas
    """
    return [
        get_repo_info,
        get_file_content,
        list_pull_requests,
        get_pr_diff,
        list_issues,
        search_code,
    ]

