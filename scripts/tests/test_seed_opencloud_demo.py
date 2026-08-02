from __future__ import annotations

import pytest


class TestValidateDemoBaseUrl:
    """AK aus specs/features/0009-local-opencloud-demo-stack.md: die Ziel-OPENCLOUD_BASE_URL wird
    vor dem Schreiben gegen ein erwartetes Demo-Muster geprueft, damit ein versehentlicher Lauf
    gegen die produktive .env keine Fotos in einen echten Familien-Space schreibt."""

    @pytest.mark.parametrize(
        "base_url",
        [
            "http://opencloud-demo:9200",
            "http://localhost:9200",
            "http://127.0.0.1:9200",
            "http://localhost:9200/",
        ],
    )
    def test_accepts_known_demo_hosts(self, seed_module, base_url: str) -> None:
        seed_module.validate_demo_base_url(base_url)  # muss NICHT werfen

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://cloud.example.com",
            "http://cloud.example.com:9200",
            "https://opencloud-demo:9200",  # falsches Schema trotz erlaubtem Host
            "http://192.168.1.50:9200",
            "not-a-url",
            "",
        ],
    )
    def test_rejects_non_demo_hosts(self, seed_module, base_url: str) -> None:
        with pytest.raises(seed_module.SeedError):
            seed_module.validate_demo_base_url(base_url)
