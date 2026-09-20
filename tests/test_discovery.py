import unittest
from gold_workspace.discovery import source_parts, repeated_lines, tokens


class DiscoveryTests(unittest.TestCase):
    def test_duplicate_image_sizes_do_not_multiply_weight(self):
        row = {'text': 'compiler', 'attachments': [
            {'url': 'https://pbs.twimg.com/media/example.jpg', 'role': 'image', 'text': 'compiler optimization'},
            {'url': 'https://pbs.twimg.com/media/example?format=jpg&name=small', 'role': 'image', 'text': 'compiler optimization'}]}
        _, sources = source_parts(row, set())
        self.assertEqual(len(sources), 1)

    def test_boilerplate_removed_only_from_derived_signal(self):
        rows = [{'text': 'Algorithms matter', 'attachments': [{'url': f'https://example.com/{i}', 'role': 'link', 'text': 'Common navigation banner\nDynamic programming'}]} for i in range(12)]
        boilerplate = repeated_lines(rows)
        original = rows[0]['attachments'][0]['text']
        primary, attachments = source_parts(rows[0], boilerplate)
        self.assertIn('algorithms', primary)
        self.assertEqual(attachments, [])
        self.assertEqual(rows[0]['attachments'][0]['text'], original)

    def test_url_and_handle_noise_does_not_become_topic(self):
        self.assertEqual(tokens('@SomeAuthor https://t.co/ABC algorithms &amp; compilers'), ['algorithms', 'compilers'])


if __name__ == '__main__': unittest.main()
