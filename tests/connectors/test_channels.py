"""Tests for the shared ConnectorChannels channel-building helper."""

from unittest.mock import Mock, patch

from tac_google.connectors._channels import ConnectorChannels


class TestOptInChannels:
    def test_no_channels_built_when_no_configs_given(self):
        channels = ConnectorChannels(tac=Mock())

        assert channels.voice is None
        assert channels.sms is None
        assert channels.rcs is None
        assert channels.whatsapp is None
        assert channels.chat is None
        assert channels.messaging == []

    def test_voice_built_when_voice_config_given(self):
        with patch("tac_google.connectors._channels.VoiceChannel") as mock_voice_channel:
            tac = Mock()
            voice_config = Mock()
            channels = ConnectorChannels(tac=tac, voice_config=voice_config)

        mock_voice_channel.assert_called_once_with(tac=tac, config=voice_config)
        assert channels.voice is mock_voice_channel.return_value
        # Voice isn't a messaging channel — it's not in .messaging.
        assert channels.messaging == []

    def test_sms_built_when_sms_config_given(self):
        with patch("tac_google.connectors._channels.SMSChannel") as mock_sms_channel:
            tac = Mock()
            sms_config = Mock()
            channels = ConnectorChannels(tac=tac, sms_config=sms_config)

        mock_sms_channel.assert_called_once_with(tac=tac, config=sms_config)
        assert channels.sms is mock_sms_channel.return_value
        assert channels.messaging == [mock_sms_channel.return_value]

    def test_rcs_built_when_rcs_config_given(self):
        with patch("tac_google.connectors._channels.RCSChannel") as mock_rcs_channel:
            tac = Mock()
            rcs_config = Mock()
            channels = ConnectorChannels(tac=tac, rcs_config=rcs_config)

        mock_rcs_channel.assert_called_once_with(tac=tac, config=rcs_config)
        assert channels.rcs is mock_rcs_channel.return_value
        assert channels.messaging == [mock_rcs_channel.return_value]

    def test_rcs_not_built_when_rcs_config_omitted(self):
        with patch("tac_google.connectors._channels.RCSChannel") as mock_rcs_channel:
            channels = ConnectorChannels(tac=Mock())

        mock_rcs_channel.assert_not_called()
        assert channels.rcs is None

    def test_whatsapp_built_when_whatsapp_config_given(self):
        with patch("tac_google.connectors._channels.WhatsAppChannel") as mock_whatsapp_channel:
            tac = Mock()
            whatsapp_config = Mock()
            channels = ConnectorChannels(tac=tac, whatsapp_config=whatsapp_config)

        mock_whatsapp_channel.assert_called_once_with(tac=tac, config=whatsapp_config)
        assert channels.whatsapp is mock_whatsapp_channel.return_value
        assert channels.messaging == [mock_whatsapp_channel.return_value]

    def test_whatsapp_not_built_when_whatsapp_config_omitted(self):
        with patch("tac_google.connectors._channels.WhatsAppChannel") as mock_whatsapp_channel:
            channels = ConnectorChannels(tac=Mock())

        mock_whatsapp_channel.assert_not_called()
        assert channels.whatsapp is None

    def test_chat_built_when_chat_config_given(self):
        with patch("tac_google.connectors._channels.ChatChannel") as mock_chat_channel:
            tac = Mock()
            chat_config = Mock()
            channels = ConnectorChannels(tac=tac, chat_config=chat_config)

        mock_chat_channel.assert_called_once_with(tac=tac, config=chat_config)
        assert channels.chat is mock_chat_channel.return_value
        assert channels.messaging == [mock_chat_channel.return_value]

    def test_chat_not_built_when_chat_config_omitted(self):
        channels = ConnectorChannels(tac=Mock())
        assert channels.chat is None

    def test_all_messaging_channels_enabled_collect_into_messaging_in_order(self):
        with (
            patch("tac_google.connectors._channels.SMSChannel") as mock_sms,
            patch("tac_google.connectors._channels.RCSChannel") as mock_rcs,
            patch("tac_google.connectors._channels.WhatsAppChannel") as mock_whatsapp,
            patch("tac_google.connectors._channels.ChatChannel") as mock_chat,
        ):
            channels = ConnectorChannels(
                tac=Mock(),
                sms_config=Mock(),
                rcs_config=Mock(),
                whatsapp_config=Mock(),
                chat_config=Mock(),
            )

        assert channels.messaging == [
            mock_sms.return_value,
            mock_rcs.return_value,
            mock_whatsapp.return_value,
            mock_chat.return_value,
        ]
