"""Thin wrapper around BackupManager for UI callers."""

from pathlib import Path

from er_save_manager.backup.manager import BackupManager, BackupMetadata
from er_save_manager.parser import Save


def create_backup_with_warning(
    save_path: str | Path,
    description: str = "",
    operation: str = "",
    save: Save | None = None,
) -> tuple[Path | None, list[BackupMetadata]]:
    """
    Create a backup. When the max-backup limit is exceeded, oldest files are
    removed silently; pruning is logged (see BackupManager logger), no modal.
    """
    try:
        manager = BackupManager(Path(save_path))
        return manager.create_backup(
            description=description,
            operation=operation,
            save=save,
        )
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return None, []
