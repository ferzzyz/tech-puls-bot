import os
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from news_card import render_card


class Cards(unittest.TestCase):
    def test_russian_titles(self):
        for category in ('ai', 'gadgets', 'it'):
            with self.subTest(category=category):
                data = render_card('Ёж и ёлка: ' + 'Сверхдлинноеслово' * 20, '', category)
                with Image.open(BytesIO(data)) as photo:
                    self.assertEqual((photo.format, photo.size), ('JPEG', (1280, 720)))
                    photo.load()

    def test_renderer_failure_uses_original_photo_then_text(self):
        with patch.dict(os.environ, TELEGRAM_BOT_TOKEN='test', TELEGRAM_CHANNEL_ID='test'):
            import publish
        with patch('news_card.render_card', side_effect=OSError('missing font')), \
             patch.object(publish, 'send_photo_file') as photo, \
             patch.object(publish, 'telegram_call') as message:
            publish.publish('Подпись', 'https://example.org/photo.jpg', 'Заголовок')
            photo.assert_called_once()
            message.assert_not_called()
            photo.side_effect = ValueError('unavailable')
            publish.publish('Подпись', 'https://example.org/photo.jpg', 'Заголовок')
            self.assertEqual(message.call_args.args[0], 'sendMessage')
