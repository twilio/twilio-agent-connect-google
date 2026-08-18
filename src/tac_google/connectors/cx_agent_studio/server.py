"""FastAPI server for CX Agent Studio voice — ConversationRelay or S2S.

`TACFastAPIServer.voice_channel` only accepts `VoiceChannel`, and
`VoiceS2SChannel` isn't one (it just exposes the same
`handle_incoming_call`/`handle_websocket` shape). This subclass accepts
either type and dispatches on `isinstance`: a `VoiceChannel` goes to
`TACFastAPIServer` as usual; a `VoiceS2SChannel` gets its own routes
registered here instead.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Response, WebSocket
from tac.channels.messaging import MessagingChannel
from tac.channels.voice import VoiceChannel
from tac.core.tac import TAC
from tac.server import (
    FastAPIWebSocketAdapter,
    TACServerConfig,
    build_http_signature_dependency,
    build_websocket_signature_dependency,
)
from tac.server.fastapi_server import TACFastAPIServer

from tac_google.connectors.cx_agent_studio.voice_s2s.channel import VoiceS2SChannel


class CXAgentStudioFastAPIServer(TACFastAPIServer):
    """`TACFastAPIServer` plus support for native speech-to-speech voice.

    Args:
        tac: TAC instance.
        voice_channel: Pass a `VoiceChannel` for ConversationRelay voice, a
            `VoiceS2SChannel` for native speech-to-speech voice, or None for
            no voice channel at all.
        messaging_channels: Messaging channels (SMS, etc.), same as
            `TACFastAPIServer`.
        config: `TACServerConfig`, same as `TACFastAPIServer`.
        app: Existing `FastAPI` app to register routes onto, same as
            `TACFastAPIServer`.
    """

    def __init__(
        self,
        tac: TAC,
        voice_channel: VoiceChannel | VoiceS2SChannel | None = None,
        messaging_channels: list[MessagingChannel] | None = None,
        config: TACServerConfig | None = None,
        app: FastAPI | None = None,
    ) -> None:
        self.voice_s2s_channel: VoiceS2SChannel | None = None
        crelay_voice_channel: VoiceChannel | None = None

        if isinstance(voice_channel, VoiceS2SChannel):
            self.voice_s2s_channel = voice_channel
        elif isinstance(voice_channel, VoiceChannel):
            crelay_voice_channel = voice_channel
        elif voice_channel is not None:
            raise TypeError(
                f"voice_channel must be a VoiceChannel, a VoiceS2SChannel, or None — "
                f"got {type(voice_channel).__name__}."
            )

        super().__init__(
            tac=tac,
            voice_channel=crelay_voice_channel,
            messaging_channels=messaging_channels,
            config=config,
            app=app,
        )

    def _register_routes(self, app: FastAPI) -> None:
        super()._register_routes(app)
        if self.voice_s2s_channel is None:
            return

        vc = self.voice_s2s_channel
        http_sig = build_http_signature_dependency(self.tac.config.auth_token)
        ws_sig = build_websocket_signature_dependency(self.tac.config.auth_token)

        @app.post(self.config.twiml_path, dependencies=[Depends(http_sig)])
        async def s2s_twiml() -> Response:
            """Generate TwiML that connects the call to Twilio Media Streams."""
            xml = await vc.handle_incoming_call()
            return Response(content=xml, media_type="application/xml")

        @app.websocket(self.tac.config.voice_websocket_path)
        async def s2s_media_stream(websocket: WebSocket, _: None = Depends(ws_sig)) -> None:
            """Bridge the call's Twilio Media Streams connection to CES BidiRunSession."""
            await vc.handle_websocket(FastAPIWebSocketAdapter(websocket))
