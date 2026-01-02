"""IPC 메서드 핸들러"""

from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
import logging
import threading

from .protocol import JsonRpcError, METHOD_NOT_FOUND, INTERNAL_ERROR

if TYPE_CHECKING:
    from ..main import EmojiClicker

logger = logging.getLogger(__name__)


@dataclass
class DownloadState:
    """다운로드 상태 관리"""
    is_downloading: bool = False
    downloaded: int = 0
    total: int = 0
    cancel_requested: bool = False
    error: Optional[str] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def start(self):
        with self._lock:
            self.is_downloading = True
            self.downloaded = 0
            self.total = 0
            self.cancel_requested = False
            self.error = None

    def update(self, downloaded: int, total: int):
        with self._lock:
            self.downloaded = downloaded
            self.total = total

    def finish(self, error: Optional[str] = None):
        with self._lock:
            self.is_downloading = False
            self.error = error

    def request_cancel(self):
        with self._lock:
            self.cancel_requested = True

    def should_cancel(self) -> bool:
        with self._lock:
            return self.cancel_requested

    def get_progress(self) -> dict:
        with self._lock:
            return {
                "is_downloading": self.is_downloading,
                "downloaded": self.downloaded,
                "total": self.total,
                "percent": (self.downloaded / self.total * 100) if self.total > 0 else 0,
                "error": self.error,
            }


# 전역 다운로드 상태
_download_state = DownloadState()


class MethodHandlers:
    """메서드 핸들러 디스패처"""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._clicker: Optional["EmojiClicker"] = None
        self._progress_callback: Optional[Callable[[int, int], None]] = None

    def set_clicker(self, clicker: "EmojiClicker"):
        """EmojiClicker 인스턴스 설정"""
        self._clicker = clicker

    def set_progress_callback(self, callback: Callable[[int, int], None]):
        """진행률 콜백 설정 (downloaded, total)"""
        self._progress_callback = callback

    def notify_progress(self, downloaded: int, total: int):
        """진행률 알림"""
        if self._progress_callback:
            self._progress_callback(downloaded, total)

    def register(self, method: str):
        """핸들러 데코레이터"""
        def decorator(func: Callable):
            self._handlers[method] = func
            return func
        return decorator

    async def dispatch(self, method: str, params: Any = None) -> Any:
        """메서드 호출"""
        handler = self._handlers.get(method)
        if handler is None:
            raise JsonRpcError(METHOD_NOT_FOUND, f"Method not found: {method}")

        try:
            # 핸들러 호출 (clicker 인스턴스 전달)
            return await handler(self._clicker, params)
        except JsonRpcError:
            raise
        except Exception as e:
            logger.exception(f"Handler error for {method}")
            raise JsonRpcError(INTERNAL_ERROR, str(e))


# 전역 핸들러 인스턴스
_handlers = MethodHandlers()


def create_handlers() -> MethodHandlers:
    """핸들러 인스턴스 반환"""
    return _handlers


# === 핸들러 등록 ===

@_handlers.register("get_status")
async def handle_get_status(clicker: "EmojiClicker", params: Any) -> dict:
    """현재 상태 조회"""
    if clicker is None:
        return {"connected": False, "mode": "unknown", "chat_active": False}

    return {
        "connected": True,
        "mode": _get_current_mode(clicker),
        "chat_active": clicker._current_chat_hwnd is not None,
    }


@_handlers.register("get_settings")
async def handle_get_settings(clicker: "EmojiClicker", params: Any) -> dict:
    """설정 조회"""
    from ..settings import get_settings
    settings = get_settings()
    return {
        "hotkeys": {
            name: {"modifiers": hk["modifiers"], "key": hk["key"]}
            for name, hk in settings.get_all_hotkeys().items()
        }
    }


@_handlers.register("set_hotkey")
async def handle_set_hotkey(clicker: "EmojiClicker", params: Any) -> bool:
    """핫키 변경"""
    from ..settings import get_settings

    if not isinstance(params, dict):
        raise JsonRpcError(-32602, "Invalid params: expected object")

    name = params.get("name")
    modifiers = params.get("modifiers", [])
    key = params.get("key")

    if not name or not key:
        raise JsonRpcError(-32602, "Missing required fields: name, key")

    settings = get_settings()
    settings.set_hotkey(name, modifiers, key)
    settings.save()

    # 핫키 동적 재등록
    if clicker is not None and hasattr(clicker, "hotkey_manager"):
        clicker.hotkey_manager.update_hotkey(name)
        logger.info(f"Hotkey updated: {name} -> {modifiers}+{key}")
    else:
        logger.warning(f"Hotkey changed but manager unavailable: {name}")

    return True


@_handlers.register("check_update")
async def handle_check_update(clicker: "EmojiClicker", params: Any) -> Optional[dict]:
    """업데이트 확인"""
    from ..updater import check_for_update

    info = check_for_update()
    if info is None:
        return None

    return {
        "version": info.version,
        "current_version": info.current_version,
        "release_notes": info.release_notes,
        "download_url": info.download_url,
    }


@_handlers.register("start_download")
async def handle_start_download(clicker: "EmojiClicker", params: Any) -> dict:
    """다운로드 시작"""
    import asyncio
    from ..updater import UpdateInfo, start_download

    if not isinstance(params, dict):
        raise JsonRpcError(-32602, "Invalid params")

    url = params.get("url")
    if not url:
        raise JsonRpcError(-32602, "Missing download_url")

    # 이미 다운로드 중이면 에러
    if _download_state.is_downloading:
        raise JsonRpcError(-32603, "Download already in progress")

    # 임시 UpdateInfo 생성
    update_info = UpdateInfo(
        version=params.get("version", "unknown"),
        current_version=params.get("current_version", ""),
        release_notes="",
        download_url=url,
    )

    # 다운로드 시작
    _download_state.start()

    # 진행률 콜백 - 상태 업데이트 + 취소 체크
    def progress_callback(downloaded: int, total: int) -> bool:
        _download_state.update(downloaded, total)
        if total > 0:
            percent = (downloaded / total) * 100
            logger.debug(f"Download progress: {percent:.1f}% ({downloaded}/{total})")
        # 취소 요청 시 False 반환하여 다운로드 중단
        return not _download_state.should_cancel()

    # 동기 다운로드를 비동기로 실행
    def do_download():
        return start_download(update_info, progress_callback)

    try:
        result = await asyncio.get_event_loop().run_in_executor(None, do_download)
        if _download_state.should_cancel():
            _download_state.finish("Cancelled")
            return {"success": False, "error": "Download cancelled"}
        if result:
            _download_state.finish()
            logger.info(f"Download completed: {result}")
            return {"success": True, "path": str(result)}
        else:
            _download_state.finish("Download failed")
            return {"success": False, "error": "Download failed"}
    except Exception as e:
        _download_state.finish(str(e))
        logger.exception("Download error")
        return {"success": False, "error": str(e)}


@_handlers.register("cancel_download")
async def handle_cancel_download(clicker: "EmojiClicker", params: Any) -> bool:
    """다운로드 취소"""
    if _download_state.is_downloading:
        _download_state.request_cancel()
        logger.info("Download cancel requested")
        return True
    return False


@_handlers.register("get_download_progress")
async def handle_get_download_progress(clicker: "EmojiClicker", params: Any) -> dict:
    """다운로드 진행률 조회"""
    return _download_state.get_progress()


@_handlers.register("apply_update")
async def handle_apply_update(clicker: "EmojiClicker", params: Any) -> bool:
    """업데이트 적용 및 재시작"""
    from pathlib import Path
    from ..updater import apply_and_restart

    if not isinstance(params, dict):
        raise JsonRpcError(-32602, "Invalid params")

    zip_path = params.get("path")
    if not zip_path:
        raise JsonRpcError(-32602, "Missing path parameter")

    try:
        success = apply_and_restart(Path(zip_path))
        return success
    except Exception as e:
        logger.exception("Failed to apply update")
        raise JsonRpcError(INTERNAL_ERROR, f"Failed to apply update: {e}")


@_handlers.register("quit")
async def handle_quit(clicker: "EmojiClicker", params: Any) -> bool:
    """종료 요청"""
    import asyncio

    if clicker is not None:
        # 정리 작업 후 종료
        asyncio.get_event_loop().call_later(0.1, clicker.cleanup)

    return True


def _get_current_mode(clicker: "EmojiClicker") -> str:
    """현재 모드 문자열 반환"""
    if hasattr(clicker, "_in_context_menu_mode") and clicker._in_context_menu_mode:
        return "context_menu"
    if hasattr(clicker, "_in_navigation_mode") and clicker._in_navigation_mode:
        return "navigation"
    if hasattr(clicker, "_in_selection_mode") and clicker._in_selection_mode:
        return "selection"
    return "normal"
