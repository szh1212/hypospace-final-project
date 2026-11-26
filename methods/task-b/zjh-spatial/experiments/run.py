"""Run Jianghan Zhao's methods with the team's unchanged benchmark runner."""

from pathlib import Path
import sys


METHOD = Path(__file__).resolve().parents[1]
PROJECT = next(p for p in METHOD.parents if (p / ".git").exists())
sys.path[:0] = [str(METHOD / 'src'), str(PROJECT / 'src')]

import hypospace_runner
from spatial_codec import cyclic, decode_cyclic, decode_row_major, output_schema, row_major


DECODERS = {row_major: decode_row_major, cyclic: decode_cyclic}


class SpatialRecordedClient(hypospace_runner.RecordedClient):
    """Capture both the model's code and the corresponding scored Layer text."""

    def __init__(self, cfg, mode, folder, obs, seed, method):
        super().__init__(cfg, mode, folder, obs, seed, method)
        decoder = DECODERS.get(method)
        if self.local is not None and decoder is not None:
            self._decoder = decoder
            self._make_request = self.local.request
            self._generate_raw = self.local.generate
            self.local.request = self._constrain_request
            self.local.generate = self._generate_and_decode

    def _constrain_request(self, prompt, seed):
        request = self._make_request(prompt, seed)
        return dict(request, format=output_schema(self.obs['observation'].count('1')))

    def _generate_and_decode(self, request):
        generated = self._generate_raw(request)
        raw = generated['response']
        context = {'observation': self.obs['observation'], 'query_index': len(self.records)}
        scored = self._decoder(raw, context)
        return dict(generated, raw_response=raw, response=scored, code_decoded=scored != raw)


if __name__ == '__main__':
    hypospace_runner.RecordedClient = SpatialRecordedClient
    hypospace_runner.main()
