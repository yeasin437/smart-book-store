"""Reset ONLY the local bookstore super-user for fresh first-admin enrollment.

Put this file next to main.py in the extracted Lumina Smart Bookstore project.
Close the bookstore before running. Uses only Python's standard library.
"""
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / 'data' / 'bookstore.sqlite3'
FACES = ROOT / 'data' / 'faces'


def main():
    print('Lumina Smart Bookstore - reset super-user ONLY')
    if not (ROOT / 'main.py').is_file() or not DB_PATH.is_file():
        print('ERROR: Put this script in the project folder next to main.py.')
        print('Expected database:', DB_PATH)
        return 1

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        admins = conn.execute("SELECT id, username FROM users WHERE role = 'SU'").fetchall()
        if not admins:
            print('There is no existing super-user to reset. Start main.py to create one.')
            return 0
        if len(admins) != 1:
            print('ERROR: Unexpected multiple super-user accounts. Nothing changed.')
            return 1
        admin = admins[0]
        admin_id = admin['id']
        username = admin['username']

        # Unexpected historical purchases are not removed or reassigned.
        linked_purchases = conn.execute(
            'SELECT COUNT(*) FROM purchases WHERE user_id=?', (admin_id,)
        ).fetchone()[0]
        if linked_purchases:
            print('ERROR: This super-user has linked purchases. Nothing changed.')
            return 1

        print(f'Super-user to reset: {username} (ID {admin_id})')
        print('Other customer accounts, books, purchases, and balances will remain.')
        answer = input('Type RESET to confirm: ').strip()
        if answer != 'RESET':
            print('Cancelled. No changes made.')
            return 0

        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = ROOT / 'data' / 'backups' / f'before_superuser_reset_{stamp}'
        backup_dir.mkdir(parents=True, exist_ok=False)
        backup_db_path = backup_dir / 'bookstore.sqlite3'
        with sqlite3.connect(backup_db_path) as backup_db:
            conn.backup(backup_db)

        face_path = FACES / f'{admin_id}.npz'
        if face_path.is_file():
            shutil.copy2(face_path, backup_dir / f'face_{admin_id}.npz')

        # Detach only the super-user's references; preserve their historical
        # financial entries, page views, reviews and security records.
        try:
            with conn:
                conn.execute('UPDATE deposits SET by_user=NULL WHERE by_user=?', (admin_id,))
                conn.execute('UPDATE views SET user_id=NULL WHERE user_id=?', (admin_id,))
                conn.execute(
                    "UPDATE reviews SET user_id=NULL, guest_name=? WHERE user_id=?",
                    (f'Former admin ({username})', admin_id),
                )
                conn.execute('UPDATE security_events SET user_id=NULL WHERE user_id=?', (admin_id,))
                # Voice templates are automatically deleted (ON DELETE CASCADE).
                conn.execute("DELETE FROM users WHERE id=? AND role='SU'", (admin_id,))
        except Exception:
            print('ERROR: Database change failed. All changes rolled back.')
            print('Your backup is at:', backup_dir)
            raise

        # Remove only this former admin's biometric face template; not anyone else's.
        if face_path.is_file():
            face_path.unlink()
        print('\nSUCCESS: Only the super-user account was reset.')
        print('Customer accounts, books and customer transaction history are intact.')
        print('Backup:', backup_dir)
        print('Start the bookstore again to create a fresh super-user.')
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'ERROR: {exc}')
        sys.exit(1)
