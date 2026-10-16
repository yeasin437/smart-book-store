"""Role-filtered local RAG, Ollama fallback, and creative smart reading paths."""
import json
import math
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from . import database as db

KNOWLEDGE_DIR=db.ROOT/'knowledge'
TOKEN=re.compile(r"[a-z0-9']+")
STOP={'the','and','or','a','an','for','to','how','do','does','i','you','of','in','is','are','can','me','my','about','what','who','where','when','it','we','with','our','your','this','that','on','from','please','tell'}


def terms(t):
    return [x for x in TOKEN.findall(t.lower()) if len(x)>1 and x not in STOP]


def chunks(text, size=130, overlap=24):
    words=text.split()
    if not words: return []
    out=[]
    for i in range(0,len(words),size-overlap):
        out.append(' '.join(words[i:i+size]))
        if i+size>=len(words):break
    return out


def allowed_files(role):
    return [(path,folder) for folder,minimum in [('public',0),('registered',1),('vip',2),('admin',3)]
            if db.ROLES[role]>=minimum for path in (KNOWLEDGE_DIR/folder).glob('*.txt')]


def retrieve(query,role):
    """A compact lexical TF-IDF retriever (no paid embeddings or vector server)."""
    records=[]
    for path,folder in allowed_files(role):
        for chunk in chunks(path.read_text(encoding='utf-8',errors='replace')):
            records.append((str(path.relative_to(KNOWLEDGE_DIR)),chunk,Counter(terms(chunk))))
    q=Counter(terms(query))
    if not q or not records:return []
    df=Counter()
    for _,_,freq in records:
        df.update(freq.keys())
    n=len(records)
    scores=[]
    for name,chunk,freq in records:
        overlap=sum(q[t]*(1+math.log(1+freq[t]))*math.log(1+(n+1)/(df[t]+0.5)) for t in q if freq[t])
        if overlap>0: scores.append((overlap/math.sqrt(max(len(terms(chunk)),1)),name,chunk))
    scores.sort(reverse=True)
    # Must match at least 2 distinctive terms except for very short queries.
    matches=[]
    for score,name,chunk in scores[:3]:
        distinct=len(set(q)&set(terms(chunk)))
        if distinct >= min(2,len(q)) and score>=0.25:
            matches.append((name,chunk))
    return matches


def ollama_chat(query,role,context=None):
    role_limits={'VS':95,'RC':180,'VC':350,'SU':550}
    prompt=(f'You are a helpful smart bookstore assistant. The caller is role {role}. '
            f'Reply with at most {role_limits[role]} words. Do not pretend you accessed data that was not supplied. '
            'Never disclose private finance or account details unless supplied by a trusted system. '
            'Do not instruct users how to bypass authentication.')
    if context:
        prompt+=' Answer ONLY from the provided local excerpts. If they do not answer the question, say so.'
        query='LOCAL EXCERPTS:\n'+context+'\nQUESTION:\n'+query
    body=json.dumps({'model':os.getenv('OLLAMA_MODEL','llama3.2:1b'),
                     'messages':[{'role':'system','content':prompt},{'role':'user','content':query}],
                     'stream':False,'options':{'num_predict':min(700,role_limits[role]*3)}}).encode()
    req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=body,
                               headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=90) as response:
        return json.load(response)['message']['content'].strip()


def ask(question,role='VS'):
    question=question.strip()
    if not question:return 'Please enter your question.'
    if role not in db.ROLES:raise ValueError('Invalid role.')
    finance_terms={'finance','financial','revenue','profit','sales','income','earnings','money report','total purchases','total deposits','all balances','balance report'}
    financial=any(p in question.lower() for p in finance_terms)
    if financial:
        if role!='SU':
            return '[ACCESS DENIED] Only the super-user can view system-wide financial reports.'
        f=db.finance_report()
        return ('[SYSTEM FINANCE - SU ONLY]\n'
                f"Transactions: {f['purchases']}\nSales: {db.currency(f['sales_cents'])}\n"
                f"Overdraft fines assessed: {db.currency(f['fines_cents'])}\n"
                f"Customer deposits (wallet funding, not sales): {db.currency(f['deposits_cents'])}\n"
                f"Net customer wallet balances: {db.currency(f['wallet_balances_cents'])}\n"
                'Sales and fines are reported separately; deposits are not counted as sales.')
    docs=retrieve(question,role)
    if docs:
        context='\n\n'.join('SOURCE '+p+'\n'+chunk for p,chunk in docs)
        citations=', '.join(dict.fromkeys(path for path,_ in docs))
        try:
            answer=ollama_chat(question,role,context)
        except (urllib.error.URLError,TimeoutError,KeyError,OSError):
            answer='Matching local information (extract):\n'+docs[0][1]
        return f'[RAG - local documents: {citations}]\n{answer}'
    try:
        return '[LLM - Ollama local model]\n'+ollama_chat(question,role)
    except urllib.error.HTTPError as e:
        if e.code==404:
            return '[LLM UNAVAILABLE] The Ollama model is missing. Run: ollama pull '+os.getenv('OLLAMA_MODEL','llama3.2:1b')
        return f'[LLM UNAVAILABLE] Ollama HTTP error {e.code}. Check Ollama is running.'
    except (urllib.error.URLError,TimeoutError,KeyError,OSError):
        return '[LLM UNAVAILABLE] Install/start Ollama and run: ollama pull '+os.getenv('OLLAMA_MODEL','llama3.2:1b')


def reading_path(user_id=None,topic=''):
    """Creative feature: adaptive 3-book reading journey with explanations."""
    books=db.all_books()
    if not books:return []
    selected=[]
    history=db.rows('''SELECT b.category,COUNT(*) AS n FROM books b JOIN views v ON b.id=v.book_id
        WHERE v.user_id=? GROUP BY b.category ORDER BY n DESC''',(user_id,)) if user_id else []
    favored=history[0]['category'] if history else ''
    q=topic.lower().strip()
    matches=[]
    for book in books:
        relevance=(6 if q and q in (book['title']+' '+book['description']+' '+book['category']).lower() else 0)
        relevance+=3 if book['category']==favored else 0
        matches.append((relevance,book))
    matches.sort(key=lambda t:(-t[0],t[1]['published_year'],t[1]['title']))
    first=matches[0][1]
    selected.append((first,'Start with this entry point to the topic or your interests.'))
    related=[b for b in books if b['category']==first['category'] and b['id']!=first['id']]
    for b in related[:2]:
        selected.append((b,'Build on the same genre and compare writing styles or ideas.'))
    if len(selected)<3:
        for _,b in matches[1:]:
            if b['id'] not in [x['id'] for x,_ in selected]:
                selected.append((b,'Explore a contrasting perspective to expand your reading.'))
            if len(selected)==3:break
    return selected
