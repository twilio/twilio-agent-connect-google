"""Tests for the shared ConnectorChannels channel-building helper."""

from unittest.mock import Mock, patch

from tac_google.connectors._channels import ConnectorChannels


def make_tac(rcs_sender_id: str | None = None, whatsapp_number: str | None = None) -> Mock:
    tac = Mock()
    tac.config = Mock(rcs_sender_id=rcs_sender_id, whatsapp_number=whatsapp_number)
    return tac


class TestSmsAndChatAlwaysBuilt:
    def test_sms_built_even_with_no_config(self):
        with patch("tac_google.connectors._channels.SMSChannel") as mock_sms_channel:
            tac = make_tac()
            channels = ConnectorChannels(tac=tac)

        mock_sms_channel.assert_called_once_with(tac=tac, config=None)
        assert channels.sms is mock_sms_channel.return_value

    def test_chat_built_even_with_no_config(self):
        with patch("tac_google.connectors._channels.ChatChannel") as mock_chat_channel:
            tac = make_tac()
            channels = ConnectorChannels(tac=tac)

        mock_chat_channel.assert_called_once_with(tac=tac, config=None)
        assert channels.chat is mock_chat_channel.return_value


class TestRcsAndWhatsappGatedOnResource:
    def test_rcs_built_when_rcs_sender_id_configured(self):
        with patch("tac_google.connectors._channels.RCSChannel") as mock_rcs_channel:
            tac = make_tac(rcs_sender_id="rcs_sender_123")
            rcs_config = Mock()
            channels = ConnectorChannels(tac=tac, rcs_config=rcs_config)

        mock_rcs_channel.assert_called_once_with(tac=tac, config=rcs_config)
        assert channels.rcs is mock_rcs_channel.return_value

    def test_rcs_not_built_when_rcs_sender_id_not_configured_even_with_config_passed(self):
        with patch("tac_google.connectors._channels.RCSChannel") as mock_rcs_channel:
            channels = ConnectorChannels(tac=make_tac(), rcs_config=Mock())

        mock_rcs_channel.assert_not_called()
        assert channels.rcs is None

    def test_whatsapp_built_when_whatsapp_number_configured(self):
        with patch("tac_google.connectors._channels.WhatsAppChannel") as mock_whatsapp_channel:
            tac = make_tac(whatsapp_number="whatsapp:+15550001234")
            whatsapp_config = Mock()
            channels = ConnectorChannels(tac=tac, whatsapp_config=whatsapp_config)

        mock_whatsapp_channel.assert_called_once_with(tac=tac, config=whatsapp_config)
        assert channels.whatsapp is mock_whatsapp_channel.return_value

    def test_whatsapp_not_built_when_whatsapp_number_not_configured(self):
        with patch("tac_google.connectors._channels.WhatsAppChannel") as mock_whatsapp_channel:
            channels = ConnectorChannels(tac=make_tac(), whatsapp_config=Mock())

        mock_whatsapp_channel.assert_not_called()
        assert channels.whatsapp is None
