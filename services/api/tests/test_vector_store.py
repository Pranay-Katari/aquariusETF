from app.services.vector_store import _embed


def test_hashed_embedding_is_deterministic_and_normalized():
    vector = _embed("AI infrastructure and semiconductors")
    assert len(vector) == 256
    assert vector == _embed("AI infrastructure and semiconductors")
    assert round(sum(value * value for value in vector), 6) == 1.0
