import threading

from app.services import session_store


def test_concurrent_appends_survive():
    session_id = "race-appends"
    session_store.create_session(session_id, "contract.txt")

    threads = 8
    per_thread = 25
    barrier = threading.Barrier(threads)

    def worker():
        barrier.wait()
        for i in range(per_thread):
            session_store.append_transcript(
                session_id,
                {"timestamp": "x", "mode": "live", "chunk_index": i, "text": "x"},
            )

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()

    assert len(session_store.get_transcript(session_id)) == threads * per_thread


def test_concurrent_append_and_finding_do_not_lose_entries():
    session_id = "race-mixed"
    session_store.create_session(session_id, "contract.txt")

    n_appends = 50
    n_findings = 50
    barrier = threading.Barrier(2)

    def append_worker():
        barrier.wait()
        for i in range(n_appends):
            session_store.append_transcript(
                session_id,
                {"timestamp": "x", "mode": "live", "chunk_index": i, "text": "x"},
            )

    def finding_worker():
        barrier.wait()
        for i in range(n_findings):
            session_store.add_finding(session_id, {"issue_question": f"q{i}"})

    a = threading.Thread(target=append_worker)
    f = threading.Thread(target=finding_worker)
    a.start()
    f.start()
    a.join()
    f.join()

    data = session_store.load_session(session_id)
    assert len(data["transcript"]) == n_appends
    assert len(data["findings"]) == n_findings
