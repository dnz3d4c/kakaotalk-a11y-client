"""Named Pipe IPC 서버"""

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from .protocol import JsonRpcMessage, JsonRpcError, PARSE_ERROR
from .handlers import MethodHandlers

if TYPE_CHECKING:
    from ..main import EmojiClicker

logger = logging.getLogger(__name__)

PIPE_NAME = r"\\.\pipe\kakaotalk-a11y-ipc"


class IPCServer:
    """Named Pipe IPC 서버"""

    def __init__(self, handlers: MethodHandlers):
        self.handlers = handlers
        self._running = False
        self._pipe = None
        self._clients: list = []

    async def start(self, clicker: Optional["EmojiClicker"] = None):
        """서버 시작"""
        import win32pipe
        import win32file
        import pywintypes

        self.handlers.set_clicker(clicker)
        self._running = True

        logger.info(f"IPC server starting on {PIPE_NAME}")
        print(f"[IPC] Starting server on {PIPE_NAME}", flush=True)

        while self._running:
            try:
                # Named Pipe 생성
                print(f"[IPC] Creating pipe...", flush=True)
                pipe = win32pipe.CreateNamedPipe(
                    PIPE_NAME,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE
                    | win32pipe.PIPE_READMODE_MESSAGE
                    | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    4096,  # out buffer
                    4096,  # in buffer
                    0,  # timeout
                    None,  # security
                )
                print(f"[IPC] Pipe created, waiting for client...", flush=True)

                logger.debug("Waiting for client connection...")

                # 클라이언트 연결 대기 (블로킹 - 별도 스레드에서 실행)
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: win32pipe.ConnectNamedPipe(pipe, None)
                )

                logger.info("Client connected")

                # 클라이언트 처리
                asyncio.create_task(self._handle_client(pipe))

            except pywintypes.error as e:
                if e.winerror == 232:  # ERROR_NO_DATA - 클라이언트 연결 끊김
                    continue
                logger.error(f"Pipe error: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.exception(f"Server error: {e}")
                await asyncio.sleep(1)

    async def _handle_client(self, pipe):
        """클라이언트 연결 처리"""
        import win32file
        import pywintypes

        try:
            while self._running:
                # 메시지 읽기
                try:
                    result, data = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: win32file.ReadFile(pipe, 4096)
                    )
                    if not data:
                        break

                    message = data.decode("utf-8").strip()
                    if not message:
                        continue

                    logger.debug(f"Received: {message}")

                    # 요청 처리
                    response = await self._process_message(message)

                    # 응답 전송
                    if response:
                        response_bytes = (response + "\n").encode("utf-8")
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: win32file.WriteFile(pipe, response_bytes)
                        )
                        logger.debug(f"Sent: {response}")

                except pywintypes.error as e:
                    if e.winerror in (109, 232):  # ERROR_BROKEN_PIPE, ERROR_NO_DATA
                        logger.debug("Client disconnected")
                        break
                    raise

        except Exception as e:
            logger.exception(f"Client handler error: {e}")
        finally:
            try:
                import win32file
                win32file.CloseHandle(pipe)
            except:
                pass
            logger.debug("Client connection closed")

    async def _process_message(self, message: str) -> Optional[str]:
        """메시지 처리 및 응답 생성"""
        try:
            request = JsonRpcMessage.from_json(message)
        except JsonRpcError as e:
            return JsonRpcMessage.error_response(None, e).to_json()

        # Notification (id 없음) - 응답 불필요
        if request.id is None:
            if request.method:
                try:
                    await self.handlers.dispatch(request.method, request.params)
                except Exception as e:
                    logger.error(f"Notification handler error: {e}")
            return None

        # Request - 응답 필요
        try:
            result = await self.handlers.dispatch(request.method, request.params)
            return JsonRpcMessage.success(request.id, result).to_json()
        except JsonRpcError as e:
            return JsonRpcMessage.error_response(request.id, e).to_json()

    async def send_notification(self, method: str, params=None):
        """알림 전송 (현재 미사용 - 폴링 방식으로 대체됨)"""
        notification = JsonRpcMessage.notification(method, params)
        message = notification.to_json() + "\n"
        logger.debug(f"Notification (not sent): {message}")

    def stop(self):
        """서버 중지"""
        self._running = False
        logger.info("IPC server stopping")
