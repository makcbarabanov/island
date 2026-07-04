-- Явная привязка книги к шагу чтения (опционально)
ALTER TABLE dream_books
  ADD COLUMN IF NOT EXISTS linked_step_id INT NULL REFERENCES dreams_steps(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_dream_books_linked_step_id
  ON dream_books(linked_step_id);
