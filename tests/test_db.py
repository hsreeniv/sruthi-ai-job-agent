from src.db import init_db, save_job, list_jobs

def test_save_job_deduplicates(tmp_path, monkeypatch):
    import src.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    init_db()
    save_job("QA Intern", "Example Co", "Bengaluru", "https://example.com/job/1", "test", "Python")
    save_job("QA Intern", "Example Co", "Bengaluru", "https://example.com/job/1", "test", "Python")
    assert len(list_jobs()) == 1
