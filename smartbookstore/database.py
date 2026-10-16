"""Persistent bookstore rules. All balances/prices are stored in integer cents."""
from __future__ import annotations
import hashlib
import hmac
import os
import re
import secrets
import shutil
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv('BOOKSTORE_DATA_DIR', str(ROOT / 'data')))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = DATA_DIR / 'bookstore.sqlite3'
ROLES = {'SU': 3, 'VC': 2, 'RC': 1, 'VS': 0}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def hash_pin(pin: str, salt: str | None = None):
    if not (4 <= len(pin) <= 128):
        raise ValueError('Password must have at least 4 characters.')
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', pin.encode(), bytes.fromhex(salt), 250_000).hex()


def check_pin(pin: str, stored: str):
    try:
        salt, expected = stored.split(':')
        guess = hash_pin(pin, salt).split(':')[1]
        return hmac.compare_digest(guess, expected)
    except (ValueError, TypeError):
        return False


def currency(cents: int):
    return f'${cents / 100:,.2f}'


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, tb):
        try:
            return super().__exit__(exc_type, exc_value, tb)
        finally:
            self.close()


def connect():
    con = sqlite3.connect(DB_FILE, timeout=15, factory=ClosingConnection)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=15000')
    return con


SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL COLLATE NOCASE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('SU','RC','VC')),
 balance_cents INTEGER NOT NULL DEFAULT 0, suspended INTEGER NOT NULL DEFAULT 0,
 warning_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS books (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL, category TEXT NOT NULL,
 published_year INTEGER NOT NULL, price_cents INTEGER NOT NULL CHECK(price_cents>=0),
 description TEXT NOT NULL DEFAULT '', cover_path TEXT NOT NULL DEFAULT '',
 figure_path TEXT NOT NULL DEFAULT '', stock INTEGER NOT NULL DEFAULT 10 CHECK(stock>=0),
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS views (
 id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id),
 user_id INTEGER REFERENCES users(id), viewed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS purchases (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 book_id INTEGER NOT NULL REFERENCES books(id), amount_cents INTEGER NOT NULL,
 fine_cents INTEGER NOT NULL DEFAULT 0, purchased_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS deposits (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0), by_user INTEGER REFERENCES users(id),
 deposited_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews (
 id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id),
 user_id INTEGER REFERENCES users(id), guest_name TEXT NOT NULL DEFAULT '',
 stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5), body TEXT NOT NULL,
 verified INTEGER NOT NULL DEFAULT 0, blocked INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS taboo (word TEXT PRIMARY KEY COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS guest_warnings(guest_name TEXT PRIMARY KEY COLLATE NOCASE, warning_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS voice_templates (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 features_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS security_events (
 id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT NOT NULL,
 details TEXT NOT NULL, created_at TEXT NOT NULL);
'''

SEED_BOOKS = [
 ('Pride and Prejudice','Jane Austen','Literature',1813,1299,'A classic novel of manners, relationships, and social expectations.'),
 ('Frankenstein','Mary Shelley','Science Fiction',1818,1499,'An exploration of scientific ambition and responsibility.'),
 ('The Time Machine','H. G. Wells','Science Fiction',1895,1099,'A time traveler visits far-future societies.'),
 ('The Adventures of Sherlock Holmes','Arthur Conan Doyle','Mystery',1892,1599,'Classic detective mysteries featuring Sherlock Holmes.'),
 ('Moby Dick','Herman Melville','Literature',1851,1699,'Captain Ahab searches for a legendary white whale.'),
 ('Little Women','Louisa May Alcott','Literature',1868,1399,'The March sisters grow up and pursue their dreams.'),
 ('The Wonderful Wizard of Oz','L. Frank Baum','Fantasy',1900,999,'Dorothy travels through the magical land of Oz.'),
 ('A Tale of Two Cities','Charles Dickens','History',1859,1299,'A novel set in London and Paris during the French Revolution.'),
 ('The War of the Worlds','H. G. Wells','Science Fiction',1898,1499,'A story of a Martian invasion of Earth.'),
 ('Alice’s Adventures in Wonderland','Lewis Carroll','Fantasy',1865,1099,'Alice falls down a rabbit hole into a strange world.'),
 ('The Picture of Dorian Gray','Oscar Wilde','Literature',1890,1199,'A mysterious portrait and questions about morality.'),
 ('The Art of War','Sun Tzu','Strategy',-500,999,'An ancient treatise on strategy and conflict.'),
]


def init_db():
    with connect() as db:
        db.executescript(SCHEMA)
        if not db.execute('SELECT 1 FROM books LIMIT 1').fetchone():
            db.executemany('''INSERT INTO books(title,author,category,published_year,price_cents,description,created_at)
                VALUES (?,?,?,?,?,?,?)''', [(*b, now()) for b in SEED_BOOKS])
            figure = ROOT / 'sample_images' / 'example_internal_figure.png'
            if figure.is_file():
                db.execute('UPDATE books SET figure_path=? WHERE id=(SELECT MIN(id) FROM books)', (str(figure),))
        if not db.execute('SELECT 1 FROM taboo LIMIT 1').fetchone():
            db.executemany('INSERT INTO taboo(word) VALUES(?)', [('spam',),('scam',),('idiot',),('stupid',)])


def one(sql, params=()):
    with connect() as db:
        return db.execute(sql, params).fetchone()


def rows(sql, params=()):
    with connect() as db:
        return db.execute(sql, params).fetchall()


def has_admin():
    return bool(one("SELECT 1 FROM users WHERE role='SU' LIMIT 1"))


def create_user(username, pin, role='RC', *, trusted=False):
    username = username.strip()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{2,29}', username):
        raise ValueError('Username: 3–30 letters/numbers/underscore/dot/dash; start with a letter.')
    if role not in ('RC', 'SU'):
        raise ValueError('Only normal accounts or the initial super-user may register.')
    with connect() as db:
        if role == 'SU' and (not trusted or db.execute("SELECT 1 FROM users WHERE role='SU'").fetchone()):
            raise PermissionError('Only the first super-user can be created through setup.')
        cur = db.execute('''INSERT INTO users(username,password_hash,role,created_at)
                    VALUES(?,?,?,?)''', (username, hash_pin(pin), role, now()))
        return cur.lastrowid


def delete_unenrolled_user(user_id):
    """Only for registration rollback, before purchases, reviews or login."""
    with connect() as db:
        db.execute('DELETE FROM users WHERE id=?', (user_id,))


def get_user(user_id):
    return one('SELECT * FROM users WHERE id=?', (user_id,))


def username_user(username):
    return one('SELECT * FROM users WHERE username=? COLLATE NOCASE', (username.strip(),))


def log_event(user_id, kind, details=''):
    with connect() as db:
        db.execute('INSERT INTO security_events(user_id,kind,details,created_at) VALUES(?,?,?,?)',
                   (user_id, kind, details, now()))


def login_pin_check(username, pin):
    user = username_user(username)
    if not user or not check_pin(pin, user['password_hash']):
        raise PermissionError('Username or password is incorrect.')
    if user['suspended'] or user['balance_cents'] < 0:
        raise PermissionError('This account is suspended. Ask the super-user to reopen it.')
    return user


def add_book(actor_id, title, author, category, published_year, price_cents,
             description='', cover='', figure='', stock=10):
    actor = get_user(actor_id)
    if actor is None or actor['role'] != 'SU' or actor['suspended']:
        raise PermissionError('Super-user access required.')
    if not title.strip() or not author.strip() or not category.strip() or price_cents < 0 or stock < 0:
        raise ValueError('Title, author, category, price and stock must be valid.')
    if not (-3000 <= published_year <= 2500):
        raise ValueError('Check the publication year.')
    with connect() as db:
        cur = db.execute('''INSERT INTO books(title,author,category,published_year,price_cents,
         description,cover_path,figure_path,stock,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (title.strip(), author.strip(), category.strip(), int(published_year), int(price_cents),
             description.strip(), cover, figure, int(stock), now()))
        return cur.lastrowid


def update_book(actor_id, book_id, stock=None, price_cents=None):
    if get_user(actor_id)['role'] != 'SU':
        raise PermissionError('Super-user access required.')
    with connect() as db:
        if stock is not None:
            if stock < 0: raise ValueError('Stock cannot be negative.')
            db.execute('UPDATE books SET stock=? WHERE id=?', (stock, book_id))
        if price_cents is not None:
            if price_cents < 0: raise ValueError('Price cannot be negative.')
            db.execute('UPDATE books SET price_cents=? WHERE id=?', (price_cents, book_id))


def all_books(query='', category='All', author='', year=''):
    pattern = '%' + query.lower().strip() + '%'
    clauses = ['(lower(title) LIKE ? OR lower(author) LIKE ? OR lower(description) LIKE ?)']
    p = [pattern,pattern,pattern]
    if category and category != 'All':
        clauses.append('category=?'); p.append(category)
    if author.strip():
        clauses.append('lower(author) LIKE ?'); p.append('%' + author.lower().strip() + '%')
    if year.strip():
        clauses.append('published_year=?'); p.append(int(year))
    return rows('SELECT * FROM books WHERE ' + ' AND '.join(clauses) + ' ORDER BY title', p)


def get_book(book_id):
    return one('SELECT * FROM books WHERE id=?', (book_id,))


def record_view(book_id, user_id=None):
    with connect() as db:
        db.execute('INSERT INTO views(book_id,user_id,viewed_at) VALUES(?,?,?)',
                   (book_id,user_id,now()))


def purchase(user_id, book_id):
    """Overdraft is allowed; charge an additional $1 and suspend immediately.
    Inventory and account updates occur in one transaction.
    """
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        book = db.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
        if not user or user['role'] not in ('RC','VC') or user['suspended'] or user['balance_cents'] < 0:
            raise PermissionError('Only active RC or VC customers can buy books.')
        if not book or book['stock'] <= 0:
            raise ValueError('This book is out of stock.')
        discount_price = (book['price_cents'] * 90 + 50) // 100 if user['role'] == 'VC' else book['price_cents']
        fine = 100 if discount_price > user['balance_cents'] else 0
        balance = user['balance_cents'] - discount_price - fine
        db.execute('UPDATE users SET balance_cents=?,suspended=? WHERE id=?',
                   (balance,int(balance<0),user_id))
        db.execute('UPDATE books SET stock=stock-1 WHERE id=?', (book_id,))
        db.execute('INSERT INTO purchases(user_id,book_id,amount_cents,fine_cents,purchased_at) VALUES(?,?,?,?,?)',
                   (user_id,book_id,discount_price,fine,now()))
        summary = db.execute('SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents),0) AS total FROM purchases WHERE user_id=?',
                             (user_id,)).fetchone()
        promoted = user['role']=='RC' and (summary['n'] > 3 or summary['total'] > 20000)
        if promoted:
            db.execute("UPDATE users SET role='VC' WHERE id=?", (user_id,))
        return {'charged_cents':discount_price, 'fine_cents':fine, 'balance_cents':balance,
                'suspended':bool(balance<0), 'promoted':promoted}


def deposit(actor_id, customer_id, amount_cents, reopen=False):
    if amount_cents <= 0:
        raise ValueError('Deposit must be positive.')
    actor = get_user(actor_id)
    customer = get_user(customer_id)
    if not actor or not customer or customer['role']=='SU':
        raise ValueError('Invalid account.')
    if actor_id != customer_id and actor['role'] != 'SU':
        raise PermissionError('Not allowed.')
    if reopen and actor['role'] != 'SU':
        raise PermissionError('Only super-user can reopen accounts.')
    if customer['suspended'] and actor['role'] != 'SU':
        raise PermissionError('Suspended accounts must contact the super-user.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        u = db.execute('SELECT * FROM users WHERE id=?', (customer_id,)).fetchone()
        new_balance = u['balance_cents'] + amount_cents
        if reopen and new_balance <= 0:
            raise ValueError('A reopened account must have a positive balance.')
        suspended = 0 if reopen and new_balance>0 else u['suspended']
        db.execute('UPDATE users SET balance_cents=?,suspended=? WHERE id=?', (new_balance,suspended,customer_id))
        db.execute('INSERT INTO deposits(user_id,amount_cents,by_user,deposited_at) VALUES(?,?,?,?)',
                   (customer_id,amount_cents,actor_id,now()))
    return new_balance


def taboo_words():
    return [r['word'] for r in rows('SELECT word FROM taboo ORDER BY word')]


def set_taboo(actor_id, words):
    if get_user(actor_id)['role'] != 'SU':
        raise PermissionError('Only super-user can change the taboo list.')
    cleaned = sorted(set(w.lower().strip() for w in words if re.fullmatch(r'[\w-]+',w.strip())))
    with connect() as db:
        db.execute('DELETE FROM taboo')
        db.executemany('INSERT INTO taboo(word) VALUES(?)', [(word,) for word in cleaned])


def moderate(comment, words):
    if not words:
        return comment.strip(), 0
    regex = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(w) for w in sorted(words,key=len,reverse=True)) + r')(?!\w)', re.IGNORECASE)
    matches = regex.findall(comment)
    sanitized = regex.sub(lambda m: '*'*len(m.group()), comment.strip())
    return sanitized, len(matches)


def review(book_id, stars, body, user_id=None, guest_name='Visitor'):
    if not get_book(book_id): raise ValueError('Book not found.')
    if not 1 <= stars <= 5: raise ValueError('Give 1 through 5 stars.')
    if not body.strip(): raise ValueError('Write a comment first.')
    if user_id:
        u = get_user(user_id)
        if not u or u['suspended']: raise PermissionError('Suspended users cannot review.')
    sanitized, count = moderate(body, taboo_words())
    blocked = count > 3
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        verified = bool(user_id and db.execute('SELECT 1 FROM purchases WHERE book_id=? AND user_id=? LIMIT 1',
                                               (book_id,user_id)).fetchone())
        db.execute('''INSERT INTO reviews(book_id,user_id,guest_name,stars,body,verified,blocked,created_at)
                    VALUES(?,?,?,?,?,?,?,?)''',
                   (book_id,user_id,guest_name if not user_id else '',stars,
                    '[BLOCKED: too many taboo words]' if blocked else sanitized,int(verified),int(blocked),now()))
        outcome = ''
        if blocked and user_id:
            u = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            warning = u['warning_count'] + 1
            if u['role']=='VC':
                db.execute("UPDATE users SET warning_count=?,role='RC' WHERE id=?",(warning,user_id))
                outcome = 'VIP demoted to registered customer.'
            elif u['role']=='RC':
                suspension = int(warning>2)
                db.execute('UPDATE users SET warning_count=?,suspended=? WHERE id=?',
                           (warning,suspension,user_id))
                outcome = 'Account suspended after 3 warnings.' if suspension else f'Warning {warning}/3.'
            else:
                db.execute('UPDATE users SET warning_count=? WHERE id=?',(warning,user_id))
                outcome = f'Admin warning {warning}.'
        elif blocked:
            nickname=guest_name.strip() or 'Guest'
            db.execute('INSERT INTO guest_warnings(guest_name,warning_count) VALUES(?,1) '
                       'ON CONFLICT(guest_name) DO UPDATE SET warning_count=warning_count+1',(nickname,))
            count=db.execute('SELECT warning_count FROM guest_warnings WHERE guest_name=? COLLATE NOCASE',(nickname,)).fetchone()[0]
            outcome=f'Guest nickname {nickname} warning {count}.'
        return {'blocked': blocked,'taboo_count':count,'verified':verified,'sanitized':sanitized,'outcome':outcome}


def reviews_for_book(book_id):
    return rows('''SELECT r.*, COALESCE(u.username,r.guest_name) AS reviewer FROM reviews r
             LEFT JOIN users u ON r.user_id=u.id WHERE r.book_id=? ORDER BY r.id DESC''',(book_id,))


def book_rating(book_id):
    """Return weighted mean and number of non-blocked ratings."""
    d = one('''SELECT COUNT(*) AS n,COALESCE(SUM(stars*(1+verified)),0) AS total,
              COALESCE(SUM(1+verified),0) AS weight FROM reviews WHERE book_id=? AND blocked=0''',(book_id,))
    return (d['total']/d['weight'] if d['weight'] else 0.0, d['n'])


def order_lists():
    no_order, to_order = [],[]
    for book in rows('SELECT * FROM books'):
        avg,n = book_rating(book['id'])
        if n > 3 and avg < 2: no_order.append((book,avg,n))
        if n > 3 and avg > 4: to_order.append((book,avg,n))
    return no_order,to_order


def recommendations(user_id=None):
    """Weighted purchase/view history for users; globally popular for VS and SU."""
    user = get_user(user_id) if user_id else None
    catalog = rows('SELECT * FROM books')
    stats = rows('''SELECT b.id, (SELECT COUNT(*) FROM purchases p WHERE p.book_id=b.id) AS buys,
             (SELECT COUNT(*) FROM views v WHERE v.book_id=b.id) AS browses FROM books b''')
    popular = {s['id']:10*s['buys']+s['browses'] for s in stats}
    if user is None or user['role']=='SU':
        return sorted(catalog,key=lambda b:(-popular[b['id']],b['title']))[:3]
    seen = rows('''SELECT b.category,b.author,(2*COALESCE(p.n,0)+COALESCE(v.n,0)) AS strength FROM books b
       LEFT JOIN (SELECT book_id,COUNT(*) n FROM purchases WHERE user_id=? GROUP BY book_id) p ON p.book_id=b.id
       LEFT JOIN (SELECT book_id,COUNT(*) n FROM views WHERE user_id=? GROUP BY book_id) v ON v.book_id=b.id
       WHERE COALESCE(p.n,0)+COALESCE(v.n,0)>0''',(user_id,user_id))
    category_weights={}; author_weights={}
    for s in seen:
        category_weights[s['category']]=category_weights.get(s['category'],0)+s['strength']
        author_weights[s['author']]=author_weights.get(s['author'],0)+s['strength']
    return sorted(catalog,key=lambda b:-(popular[b['id']]+8*category_weights.get(b['category'],0)+
                             5*author_weights.get(b['author'],0)))[:3]


def user_list():
    return rows('SELECT id,username,role,balance_cents,suspended,warning_count FROM users ORDER BY id')


def finance_report():
    sales = one('SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents),0) AS amount,COALESCE(SUM(fine_cents),0) AS fines FROM purchases')
    deposits = one('SELECT COALESCE(SUM(amount_cents),0) AS total FROM deposits')
    liabilities = one('SELECT COALESCE(SUM(balance_cents),0) AS balance FROM users WHERE role != "SU"')
    return {'purchases':sales['n'], 'sales_cents':sales['amount'],'fines_cents':sales['fines'],
            'deposits_cents':deposits['total'],'wallet_balances_cents':liabilities['balance']}


def purchase_history(user_id):
    return rows('''SELECT p.*,b.title FROM purchases p JOIN books b ON p.book_id=b.id
      WHERE p.user_id=? ORDER BY p.id DESC''',(user_id,))


def copy_image(path, kind='covers'):
    if not path: return ''
    source = Path(path)
    if not source.is_file(): raise FileNotFoundError(path)
    if source.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.bmp'):
        raise ValueError('Use a PNG, JPEG, WEBP or BMP image.')
    # Verify bytes are an actual supported image before copying.
    from PIL import Image
    with Image.open(source) as im: im.verify()
    target = DATA_DIR / kind
    target.mkdir(parents=True, exist_ok=True)
    dest = target / (uuid.uuid4().hex+source.suffix.lower())
    shutil.copy2(source,dest)
    return str(dest)
