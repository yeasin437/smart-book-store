"""Tkinter GUI for the project. Designed for Windows 10/11 with Python 3.11+."""
from __future__ import annotations
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw
from . import database as db, biometrics, intelligence, image_search

NAVY='#111827'; PANEL='#1c273a'; BLUE='#4f91ff'; GOLD='#eec86c'
PALE='#e5eaf3'; MUTED='#abbad1'; DARK='#0b1322'


def parse_money(text):
    try:
        from decimal import Decimal, ROUND_HALF_UP
        v=(Decimal(text.replace('$','').strip())*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
        if not v.is_finite(): raise ValueError()
        return int(v)
    except Exception as e:
        raise ValueError('Enter a valid amount, e.g. 12.50') from e


class BookstoreApp:
    def __init__(self,root):
        self.root=root
        root.title('Lumina • AI Smart Bookstore')
        root.geometry('1180x800');root.minsize(980,660)
        root.configure(bg=DARK)
        self.user_id=None
        self.photo=None
        self.book_photo=None
        self.selected_book=None
        self._setup_theme()
        self._build()
        self.refresh_all()
        if not db.has_admin():
            root.after(400,lambda:self.account_dialog(first_admin=True))

    @property
    def user(self):
        return db.get_user(self.user_id) if self.user_id else None

    @property
    def role(self):
        return self.user['role'] if self.user else 'VS'

    def _setup_theme(self):
        style=ttk.Style(self.root);style.theme_use('clam')
        style.configure('.',background=PANEL,foreground=PALE,font=('Segoe UI',10))
        style.configure('TFrame',background=PANEL)
        style.configure('TLabel',background=PANEL,foreground=PALE)
        style.configure('TEntry',fieldbackground='#e9eef6',foreground='#101827',padding=6)
        style.configure('TCombobox',fieldbackground='#e9eef6',foreground='#101827',padding=4)
        style.configure('TButton',background='#30415d',foreground='white',padding=(11,8),borderwidth=0)
        style.map('TButton',background=[('active','#415a7f')])
        style.configure('Accent.TButton',background=BLUE,foreground='#050b14',font=('Segoe UI',10,'bold'))
        style.map('Accent.TButton',background=[('active','#78a9ff')])
        style.configure('TNotebook',background=DARK,borderwidth=0)
        style.configure('TNotebook.Tab',background='#273247',foreground=PALE,padding=(14,11))
        style.map('TNotebook.Tab',background=[('selected',BLUE)],foreground=[('selected','#071322')])
        style.configure('Treeview',background='#172337',fieldbackground='#172337',foreground=PALE,rowheight=31)
        style.map('Treeview',background=[('selected','#395789')])
        style.configure('Treeview.Heading',background='#27374f',foreground='white',font=('Segoe UI',10,'bold'),padding=(4,7))

    def _label(self,parent,text,**kw):
        return tk.Label(parent,text=text,bg=kw.pop('bg',PANEL),fg=kw.pop('fg',PALE),
                        font=kw.pop('font',('Segoe UI',11)),**kw)

    def _frame(self,parent,**kw):
        return tk.Frame(parent,bg=kw.pop('bg',PANEL),**kw)

    def _build(self):
        header=self._frame(self.root,bg=DARK);header.pack(fill='x',padx=25,pady=(15,8))
        self._label(header,'◈  LUMINA',bg=DARK,fg=GOLD,font=('Segoe UI',23,'bold')).pack(side='left')
        self._label(header,'  AI-ENABLED SMART BOOKSTORE',bg=DARK,fg=MUTED,font=('Segoe UI',10)).pack(side='left',padx=10)
        self.session=self._label(header,'Browsing as visitor',bg=DARK,fg=PALE)
        self.session.pack(side='right',padx=(5,0))
        self.login_button=ttk.Button(header,text='Sign in / Create account',command=self.account_dialog)
        self.login_button.pack(side='right',padx=12)
        self.notebook=ttk.Notebook(self.root);self.notebook.pack(fill='both',expand=True,padx=24,pady=(0,15))
        self.pages={}
        for key,title in [('home','Home'),('catalog','Book catalog'),('reviews','Reviews'),
                          ('wallet','My wallet'),('chat','AI assistant'),('journey','Reading journey'),('admin','Super-user')]:
            page=self._frame(self.notebook)
            self.pages[key]=page;self.notebook.add(page,text=title)
        self._home_page();self._catalog_page();self._review_page();self._wallet_page()
        self._chat_page();self._journey_page();self._admin_page()
        self.status=tk.StringVar(value='Ready • Data is stored locally on your computer')
        self._label(self.root,'',bg=DARK).pack(side='left')
        tk.Label(self.root,textvariable=self.status,bg=DARK,fg=MUTED,font=('Segoe UI',9),anchor='w').pack(fill='x',padx=24,pady=(0,9))

    def _section(self,parent,title,subtitle=''):
        self._label(parent,title,font=('Segoe UI',19,'bold')).pack(anchor='w',padx=22,pady=(17,3))
        if subtitle:self._label(parent,subtitle,fg=MUTED,font=('Segoe UI',10),wraplength=900,justify='left').pack(anchor='w',padx=22,pady=(0,12))

    def _tree(self,parent,columns,height=10):
        tree=ttk.Treeview(parent,columns=list(columns),show='headings',height=height,selectmode='browse')
        for col,width in columns.items():tree.heading(col,text=col);tree.column(col,width=width,minwidth=65)
        return tree

    def _home_page(self):
        p=self.pages['home'];self._section(p,'Discover your next great read','Recommendations adapt to your browsing and purchases. Visitors see global favorites.')
        self.hero=self._label(p,'Welcome to Lumina',fg=GOLD,font=('Segoe UI',15,'bold'))
        self.hero.pack(anchor='w',padx=22,pady=(4,13))
        self.rec_frame=self._frame(p);self.rec_frame.pack(fill='x',padx=22)
        self._label(p,'HOW TO GET STARTED',fg=GOLD,font=('Segoe UI',11,'bold')).pack(anchor='w',padx=22,pady=(25,9))
        steps='1. Browse books and click a title to see its details.     2. Create an account and enroll voice or face.\n3. Add money to your wallet, buy books and leave ratings.     4. Try the AI assistant or personalized reading journey.'
        self._label(p,steps,justify='left',fg=MUTED,wraplength=950).pack(anchor='w',padx=22)
        ttk.Button(p,text='Refresh recommendations',command=self.refresh_home).pack(anchor='w',padx=22,pady=25)

    def refresh_home(self):
        for child in self.rec_frame.winfo_children(): child.destroy()
        self.hero.config(text=f'Welcome back, {self.user["username"]}!' if self.user else 'Explore as a visitor — no account required')
        for b in db.recommendations(self.user_id):
            card=self._frame(self.rec_frame,bg='#27374d',width=300,height=220)
            card.pack(side='left',fill='both',expand=True,padx=(0,12));card.pack_propagate(False)
            self._label(card,b['category'].upper(),bg='#27374d',fg=GOLD,font=('Segoe UI',9,'bold')).pack(anchor='w',padx=14,pady=(17,4))
            self._label(card,b['title'],bg='#27374d',font=('Segoe UI',14,'bold'),wraplength=240,justify='left').pack(anchor='w',padx=14)
            self._label(card,f"{b['author']}  •  {db.currency(b['price_cents'])}",bg='#27374d',fg=MUTED).pack(anchor='w',padx=14,pady=5)
            ttk.Button(card,text='See book',command=lambda book_id=b['id']:self.view_book(book_id)).pack(anchor='sw',padx=14,pady=15)

    def _catalog_page(self):
        p=self.pages['catalog'];self._section(p,'Browse and search books','Filter by title, keywords, author, category, publication year, or choose a cover/figure image.')
        search=self._frame(p);search.pack(fill='x',padx=20,pady=(0,10))
        self.search_text=tk.StringVar();self.category=tk.StringVar(value='All');self.author=tk.StringVar();self.year=tk.StringVar()
        for i,(v,w) in enumerate([(self.search_text,34),(self.author,23),(self.year,8)]):
            ttk.Entry(search,textvariable=v,width=w).pack(side='left',padx=(0,8))
        self.category_box=ttk.Combobox(search,textvariable=self.category,state='readonly',width=19)
        self.category_box.pack(side='left',padx=(0,8))
        ttk.Button(search,text='Find books',style='Accent.TButton',command=self.search_books).pack(side='left',padx=3)
        ttk.Button(search,text='Search image…',command=self.search_image).pack(side='left',padx=3)
        self._label(p,'Search fields: keywords  |  author  |  year  |  category',fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',padx=22,pady=(0,5))
        content=self._frame(p);content.pack(fill='both',expand=True,padx=20,pady=(0,14))
        left=self._frame(content);left.pack(side='left',fill='both',expand=True)
        self.book_tree=self._tree(left,{'ID':45,'Title':270,'Author':170,'Genre':120,'Year':65,'Price':70,'Stock':65},height=14)
        self.book_tree.pack(fill='both',expand=True)
        self.book_tree.bind('<<TreeviewSelect>>',self._on_book_selected)
        self.book_tree.bind('<Double-1>',lambda e:self.selected_book and self.notebook.select(self.pages['reviews']))
        self.book_detail=self._frame(content,bg='#243249',width=302)
        self.book_detail.pack(side='right',fill='y',padx=(16,0));self.book_detail.pack_propagate(False)
        self.cover_label=self._label(self.book_detail,'SELECT A BOOK',bg='#243249',fg=GOLD,font=('Segoe UI',14,'bold'))
        self.cover_label.pack(padx=14,pady=(18,10))
        self.detail_text=self._label(self.book_detail,'Browse the catalog to see a description and cover.',bg='#243249',fg=PALE,
                                     justify='left',wraplength=260)
        self.detail_text.pack(padx=12)
        self.cover_view=self._label(self.book_detail,'',bg='#243249');self.cover_view.pack(padx=10,pady=10)
        ttk.Button(self.book_detail,text='Buy selected book',style='Accent.TButton',command=self.buy_selected).pack(fill='x',padx=18,pady=7)
        ttk.Button(self.book_detail,text='Show internal figure',command=self.show_figure).pack(fill='x',padx=18,pady=7)
        ttk.Button(self.book_detail,text='Read / rate reviews',command=lambda:self.notebook.select(self.pages['reviews'])).pack(fill='x',padx=18,pady=7)

    def search_books(self):
        try:
            results=db.all_books(self.search_text.get(),self.category.get(),self.author.get(),self.year.get())
        except ValueError:
            return messagebox.showerror('Invalid year','Enter an integer year or leave it blank.')
        self._populate_books(results)
        self.status.set(f'{len(results)} books found.')

    def _populate_books(self,books):
        self.book_tree.delete(*self.book_tree.get_children())
        for b in books:
            self.book_tree.insert('', 'end',iid=str(b['id']),values=(b['id'],b['title'],b['author'],b['category'],
                            b['published_year'],db.currency(b['price_cents']),b['stock']))

    def view_book(self,book_id):
        self.notebook.select(self.pages['catalog'])
        if not self.book_tree.exists(str(book_id)):
            self.search_text.set('');self.category.set('All');self.author.set('');self.year.set('')
            self.search_books()
        self.book_tree.selection_set(str(book_id));self.book_tree.see(str(book_id))
        self._show_book(book_id)

    def _on_book_selected(self,event=None):
        selected=self.book_tree.selection()
        if selected:self._show_book(int(selected[0]))

    def _show_book(self,book_id):
        b=db.get_book(book_id)
        if not b:return
        if self.selected_book!=book_id:db.record_view(book_id,self.user_id)
        self.selected_book=book_id
        avg,n=db.book_rating(book_id)
        self.cover_label.config(text=b['title'],wraplength=270)
        self.detail_text.config(text=f"Author: {b['author']}\nGenre: {b['category']}\nPublished: {b['published_year']}\n"
                                f"Price: {db.currency(b['price_cents'])}  •  Stock: {b['stock']}\n"
                                f"Rating: {avg:.2f}/5 ({n} reviews)\n\n{b['description']}")
        try:
            path=Path(b['cover_path']) if b['cover_path'] else db.ROOT/'sample_images'/f"{book_id}.png"
            if path.exists():
                with Image.open(path) as im:
                    im.thumbnail((150,192))
                    self.book_photo=ImageTk.PhotoImage(im.copy())
                self.cover_view.config(image=self.book_photo,text='')
            else:self.cover_view.config(image='',text='No image available')
        except OSError:self.cover_view.config(image='',text='Cover unavailable')
        self.refresh_reviews()

    def search_image(self):
        path=filedialog.askopenfilename(title='Select book cover or internal figure',filetypes=[('Images','*.png *.jpg *.jpeg *.bmp *.webp')])
        if not path:return
        try:matches=image_search.image_matches(path)
        except Exception as e:return messagebox.showerror('Cannot search image',str(e))
        if not matches:return messagebox.showinfo('Image search','No covers or figures were available to compare.')
        self._populate_books([b for _,b in matches])
        self.status.set('Image matches, closest first: '+', '.join(f"{b['title']} ({64-d}/64 matching hash bits)" for d,b in matches))

    def show_figure(self):
        if not self.selected_book:return
        b=db.get_book(self.selected_book)
        if not b['figure_path'] or not Path(b['figure_path']).exists():
            return messagebox.showinfo('Internal figures','No internal figure has been uploaded for this book.')
        pop=tk.Toplevel(self.root);pop.title('Internal figure • '+b['title']);pop.geometry('620x620');pop.configure(bg=DARK)
        with Image.open(b['figure_path']) as im:
            im.thumbnail((570,550));pic=ImageTk.PhotoImage(im.copy())
        lbl=tk.Label(pop,image=pic,bg=DARK);lbl.image=pic;lbl.pack(expand=True)

    def buy_selected(self):
        if not self.selected_book:return messagebox.showinfo('Choose a book','Choose a book in the catalog.')
        if self.role not in ('RC','VC'):return messagebox.showinfo('Customer login required','Please sign in with a customer account.')
        b=db.get_book(self.selected_book);price=(b['price_cents']*90+50)//100 if self.role=='VC' else b['price_cents']
        msg=f"Buy {b['title']} for {db.currency(price)}?\nBalance: {db.currency(self.user['balance_cents'])}"
        if price>self.user['balance_cents']:msg+='\n\nInsufficient funds: purchase will proceed, a $1 fine applies, and your account will be suspended.'
        if not messagebox.askyesno('Confirm book purchase',msg):return
        try:result=db.purchase(self.user_id,self.selected_book)
        except Exception as e:return messagebox.showerror('Purchase error',str(e))
        notice=f"Charged: {db.currency(result['charged_cents'])}\nFine: {db.currency(result['fine_cents'])}\nBalance: {db.currency(result['balance_cents'])}"
        if result['promoted']:notice+='\n\nCongratulations! You are now a VIP (10% off future purchases).'
        if result['suspended']:
            notice+='\n\nAccount suspended. Ask the super-user to deposit money and reopen it.'
            self.user_id=None
        messagebox.showinfo('Purchase result',notice)
        self.refresh_all()

    def _review_page(self):
        p=self.pages['reviews'];self._section(p,'Community reviews','Purchased customers have 2× rating weight. More than 3 taboo words blocks a comment.')
        self.review_book=self._label(p,'Choose a book in the catalog first.',fg=GOLD,font=('Segoe UI',13,'bold'))
        self.review_book.pack(anchor='w',padx=22,pady=(0,7))
        outer=self._frame(p);outer.pack(fill='both',expand=True,padx=22)
        self.reviews_display=tk.Text(outer,height=14,wrap='word',bg='#142033',fg=PALE,insertbackground='white',relief='flat',font=('Segoe UI',10))
        self.reviews_display.pack(fill='both',expand=True);self.reviews_display.configure(state='disabled')
        form=self._frame(p);form.pack(fill='x',padx=22,pady=12)
        self.review_stars=tk.StringVar(value='5')
        self._label(form,'Stars (1–5)').grid(row=0,column=0,sticky='w')
        ttk.Combobox(form,textvariable=self.review_stars,values=list('12345'),state='readonly',width=6).grid(row=1,column=0,sticky='w',padx=(0,10))
        self.guest_name=tk.StringVar(value='Guest')
        self._label(form,'Guest nickname (visitors only)').grid(row=0,column=1,sticky='w')
        ttk.Entry(form,textvariable=self.guest_name,width=25).grid(row=1,column=1,sticky='w',padx=(0,10))
        self.comment=tk.StringVar()
        self._label(form,'Your review').grid(row=0,column=2,sticky='w')
        ttk.Entry(form,textvariable=self.comment,width=55).grid(row=1,column=2,sticky='we',padx=(0,10))
        ttk.Button(form,text='Post review',style='Accent.TButton',command=self.post_review).grid(row=1,column=3)
        form.columnconfigure(2,weight=1)

    def refresh_reviews(self):
        if not self.selected_book:return
        book=db.get_book(self.selected_book);avg,n=db.book_rating(self.selected_book)
        self.review_book.config(text=f"{book['title']}  •  {avg:.2f} / 5 from {n} published ratings")
        text=''
        for r in db.reviews_for_book(self.selected_book):
            if r['blocked']:continue
            text+=f"★ {'★'*int(r['stars'])}  {r['reviewer']} {'✓ VERIFIED PURCHASE' if r['verified'] else ''} | {r['created_at'][:10]}\n{r['body']}\n\n"
        self.reviews_display.config(state='normal');self.reviews_display.delete('1.0','end')
        self.reviews_display.insert('1.0',text or 'No published reviews yet. Be the first!');self.reviews_display.config(state='disabled')

    def post_review(self):
        if not self.selected_book:return messagebox.showwarning('Select book','Open a book in the catalog first.')
        try:outcome=db.review(self.selected_book,int(self.review_stars.get()),self.comment.get(),self.user_id,self.guest_name.get().strip() or 'Guest')
        except Exception as e:return messagebox.showerror('Review failed',str(e))
        if outcome['blocked']:
            messagebox.showwarning('Review blocked','More than 3 taboo words detected. '+outcome['outcome'])
        else:messagebox.showinfo('Review posted','Posted successfully. Offensive words, if any, were masked with *.'+('\nVerified purchase' if outcome['verified'] else ''))
        if self.user_id and db.get_user(self.user_id)['suspended']:
            self.user_id=None
            messagebox.showwarning('Signed out','Your account was suspended. Contact the super-user to reopen it.')
        self.comment.set('');self.refresh_all()

    def _wallet_page(self):
        p=self.pages['wallet'];self._section(p,'Account & purchases','RC and VIP customers can add simulated wallet funds. No real payments are processed.')
        self.wallet_info=self._label(p,'Sign in as a customer to view your account.',fg=GOLD,font=('Segoe UI',14,'bold'))
        self.wallet_info.pack(anchor='w',padx=22,pady=(6,15))
        row=self._frame(p);row.pack(fill='x',padx=22,pady=7)
        self.deposit_amount=tk.StringVar(value='25.00')
        self._label(row,'Deposit $').pack(side='left',padx=(0,8))
        ttk.Entry(row,textvariable=self.deposit_amount,width=18).pack(side='left',padx=8)
        ttk.Button(row,text='Add demo funds',style='Accent.TButton',command=self.deposit_self).pack(side='left',padx=10)
        self.history=self._tree(p,{'Date':170,'Book':350,'Charge':130,'Fine':100},height=11)
        self.history.pack(fill='both',expand=True,padx=22,pady=18)

    def refresh_wallet(self):
        self.history.delete(*self.history.get_children())
        u=self.user
        if not u or u['role']=='SU':
            self.wallet_info.config(text='Sign in as a registered customer or VIP to use your wallet.');return
        self.wallet_info.config(text=f"{u['username']} • {u['role']} • Balance {db.currency(u['balance_cents'])} • Warnings {u['warning_count']}")
        for p in db.purchase_history(u['id']):
            self.history.insert('','end',values=(p['purchased_at'][:16],p['title'],db.currency(p['amount_cents']),db.currency(p['fine_cents'])))

    def deposit_self(self):
        if self.role not in ('RC','VC'):return messagebox.showwarning('Sign in','Customers must sign in first.')
        try:balance=db.deposit(self.user_id,self.user_id,parse_money(self.deposit_amount.get()))
        except Exception as e:return messagebox.showerror('Deposit error',str(e))
        messagebox.showinfo('Funds added',f'New wallet balance: {db.currency(balance)} (simulated deposit)')
        self.refresh_all()

    def _chat_page(self):
        p=self.pages['chat'];self._section(p,'Ask Lumina AI','Local bookstore/team documents are searched first (RAG); other questions go to a local Ollama model.')
        self.chat_log=tk.Text(p,wrap='word',bg='#142033',fg=PALE,insertbackground='white',relief='flat',font=('Segoe UI',11),padx=16,pady=14)
        self.chat_log.pack(fill='both',expand=True,padx=22,pady=(0,8))
        self.chat_log.insert('end','Lumina: Hello! Ask me about store policies, our team, book recommendations or general reading topics.\n\n')
        self.chat_log.config(state='disabled')
        row=self._frame(p);row.pack(fill='x',padx=22,pady=(2,18))
        self.chat_question=tk.StringVar()
        chat_entry=ttk.Entry(row,textvariable=self.chat_question)
        chat_entry.pack(side='left',fill='x',expand=True,padx=(0,10))
        chat_entry.bind('<Return>',lambda e:self.send_chat())
        self.send_button=ttk.Button(row,text='Send question',style='Accent.TButton',command=self.send_chat)
        self.send_button.pack(side='right')

    def chat_append(self,text):
        self.chat_log.configure(state='normal');self.chat_log.insert('end',text+'\n\n')
        self.chat_log.see('end');self.chat_log.configure(state='disabled')

    def send_chat(self):
        question=self.chat_question.get().strip()
        if not question:return
        role=self.role
        self.chat_question.set('');self.chat_append('You: '+question)
        self.send_button.config(state='disabled');self.status.set('AI is answering... (local Ollama may take a moment)')
        def work():
            try:result=intelligence.ask(question,role)
            except Exception as e:result='Error: '+str(e)
            self.root.after(0,lambda:self.chat_done(result))
        threading.Thread(target=work,daemon=True).start()

    def chat_done(self,result):
        self.chat_append('Lumina: '+result);self.send_button.config(state='normal');self.status.set('Assistant ready.')

    def _journey_page(self):
        p=self.pages['journey'];self._section(p,'Your personal reading journey ✦','Creative AI-inspired feature: an explainable three-book learning path based on your interests and history.')
        row=self._frame(p);row.pack(fill='x',padx=22,pady=10)
        self.topic=tk.StringVar()
        ttk.Entry(row,textvariable=self.topic,width=49).pack(side='left',padx=(0,12))
        ttk.Button(row,text='Create my path',style='Accent.TButton',command=self.refresh_journey).pack(side='left')
        self.journey_text=tk.Text(p,wrap='word',height=15,bg='#142033',fg=PALE,insertbackground='white',relief='flat',font=('Segoe UI',12),padx=24,pady=22)
        self.journey_text.pack(fill='both',expand=True,padx=22,pady=(9,18))
        self.refresh_journey()

    def refresh_journey(self):
        plan=intelligence.reading_path(self.user_id,self.topic.get())
        report='A PERSONALIZED 3-BOOK JOURNEY\n\n'
        for n,(book,reason) in enumerate(plan,1):
            report+=f'{n}. {book["title"]} — {book["author"]}\n   {book["category"]}  •  {db.currency(book["price_cents"])}\n   Why: {reason}\n\n'
        report+='Tip: Every time you view or purchase a book, your recommendations can adapt.'
        self.journey_text.configure(state='normal');self.journey_text.delete('1.0','end');self.journey_text.insert('1.0',report)
        self.journey_text.configure(state='disabled')

    def _admin_page(self):
        p=self.pages['admin'];self._section(p,'Super-user console','Only SU can add books, manage accounts and taboo words, view order lists, and see financial data.')
        self.admin_content=self._frame(p);self.admin_content.pack(fill='both',expand=True,padx=22,pady=(5,18))

    def refresh_admin(self):
        for c in self.admin_content.winfo_children():c.destroy()
        if self.role!='SU':
            self._label(self.admin_content,'Sign in as the super-user to access administration.',fg=MUTED).pack(anchor='w',pady=15)
            return
        bar=self._frame(self.admin_content);bar.pack(fill='x',pady=(0,10))
        for title,callback in [('Add a book',self.add_book_dialog),('Edit stock/price',self.edit_book_dialog),
                               ('Taboo words',self.edit_taboo),('Refresh lists',self.refresh_admin)]:
            ttk.Button(bar,text=title,command=callback).pack(side='left',padx=(0,8))
        f=db.finance_report()
        self._label(self.admin_content,f"SALES {db.currency(f['sales_cents'])}     FINES {db.currency(f['fines_cents'])}     "
                    f"DEPOSITS {db.currency(f['deposits_cents'])}     PURCHASES {f['purchases']}",fg=GOLD,font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,15))
        self._label(self.admin_content,'ACCOUNT MANAGEMENT',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,6))
        self.user_tree=self._tree(self.admin_content,{'ID':50,'Username':170,'Role':75,'Balance':110,'Suspended':110,'Warnings':75},height=6)
        self.user_tree.pack(fill='x')
        for u in db.user_list():
            self.user_tree.insert('','end',iid=str(u['id']),values=(u['id'],u['username'],u['role'],db.currency(u['balance_cents']),
                                           'YES' if u['suspended'] else 'No',u['warning_count']))
        opts=self._frame(self.admin_content);opts.pack(fill='x',pady=10)
        ttk.Button(opts,text='Deposit / reopen selected account',style='Accent.TButton',command=self.reopen_user).pack(side='left')
        ttk.Button(opts,text='View finance report in chatbot',command=lambda:self.admin_chat_finance()).pack(side='left',padx=9)
        no_order,to_order=db.order_lists()
        self._label(self.admin_content,f"NO-ORDER LIST (4+ ratings, average < 2): {len(no_order)}",fg=GOLD).pack(anchor='w',pady=(16,3))
        self._label(self.admin_content,', '.join(f'{b["title"]} ({avg:.2f})' for b,avg,n in no_order) or 'None',fg=MUTED,wraplength=920,justify='left').pack(anchor='w')
        self._label(self.admin_content,f"TO-ORDER LIST (4+ ratings, average > 4): {len(to_order)}",fg=GOLD).pack(anchor='w',pady=(13,3))
        self._label(self.admin_content,', '.join(f'{b["title"]} ({avg:.2f})' for b,avg,n in to_order) or 'None',fg=MUTED,wraplength=920,justify='left').pack(anchor='w')

    def admin_chat_finance(self):
        self.notebook.select(self.pages['chat']);self.chat_question.set('Show the system finance report');self.send_chat()

    def reopen_user(self):
        selected=self.user_tree.selection()
        if not selected:return messagebox.showinfo('Select account','Select a customer in the account table.')
        user=db.get_user(int(selected[0]))
        if user['role']=='SU':return messagebox.showwarning('Not allowed','Cannot manage the SU wallet.')
        amount=simpledialog.askstring('Deposit and reopen',f"Current balance: {db.currency(user['balance_cents'])}\nEnter amount to deposit (e.g. 25.00):",parent=self.root)
        if amount is None:return
        try:
            reopen=bool(user['suspended'])
            balance=db.deposit(self.user_id,user['id'],parse_money(amount),reopen=reopen)
        except Exception as e:return messagebox.showerror('Account error',str(e))
        messagebox.showinfo('Updated',f"{user['username']} new balance: {db.currency(balance)}\n" + ('Account reopened.' if reopen else 'Deposit recorded.'))
        self.refresh_all()

    def add_book_dialog(self):
        w=tk.Toplevel(self.root);w.title('Add a new book');w.configure(bg=PANEL);w.geometry('550x610');w.transient(self.root);w.grab_set()
        fields={}
        for i,(key,default) in enumerate([('Title',''),('Author',''),('Category','Literature'),('Published year','2026'),('Price $','15.00'),('Stock','10'),('Description','')]):
            self._label(w,key).grid(row=i,column=0,padx=20,pady=8,sticky='w')
            var=tk.StringVar(value=default);fields[key]=var
            ttk.Entry(w,textvariable=var,width=42).grid(row=i,column=1,padx=10,pady=8)
        cover=tk.StringVar();figure=tk.StringVar()
        ttk.Button(w,text='Choose cover image…',command=lambda:cover.set(filedialog.askopenfilename(parent=w,filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp')]))).grid(row=7,column=0,columnspan=2,pady=7)
        ttk.Button(w,text='Choose internal figure…',command=lambda:figure.set(filedialog.askopenfilename(parent=w,filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp')]))).grid(row=8,column=0,columnspan=2,pady=7)
        def save():
            try:
                cp=db.copy_image(cover.get(),'covers') if cover.get() else ''
                fp=db.copy_image(figure.get(),'figures') if figure.get() else ''
                db.add_book(self.user_id,fields['Title'].get(),fields['Author'].get(),fields['Category'].get(),
                            int(fields['Published year'].get()),parse_money(fields['Price $'].get()),
                            fields['Description'].get(),cp,fp,int(fields['Stock'].get()))
            except Exception as e:return messagebox.showerror('Cannot add book',str(e),parent=w)
            w.destroy();self.refresh_all();messagebox.showinfo('Added','Book has been saved to your local catalog.')
        ttk.Button(w,text='Save new book',style='Accent.TButton',command=save).grid(row=9,column=0,columnspan=2,pady=18)

    def edit_book_dialog(self):
        bid=simpledialog.askinteger('Edit book','Book ID (find it in catalog):',parent=self.root,minvalue=1)
        if bid is None:return
        b=db.get_book(bid)
        if not b:return messagebox.showerror('Unknown book','That ID does not exist.')
        price=simpledialog.askstring('Update book',f"{b['title']}\nNew price in dollars:",initialvalue=f"{b['price_cents']/100:.2f}",parent=self.root)
        if price is None:return
        stock=simpledialog.askinteger('Update stock','New stock count:',initialvalue=b['stock'],parent=self.root,minvalue=0)
        if stock is None:return
        try:db.update_book(self.user_id,bid,stock=stock,price_cents=parse_money(price))
        except Exception as e:return messagebox.showerror('Error',str(e))
        self.refresh_all()

    def edit_taboo(self):
        old=', '.join(db.taboo_words())
        response=simpledialog.askstring('Taboo words','Comma-separated forbidden words:',initialvalue=old,parent=self.root)
        if response is None:return
        try:db.set_taboo(self.user_id,response.split(','))
        except Exception as e:return messagebox.showerror('Error',str(e))
        messagebox.showinfo('Updated','Taboo words updated.')

    def account_dialog(self,first_admin=False):
        if not db.has_admin():first_admin=True
        if self.user_id and not first_admin:
            self.user_id=None;self.selected_book=None;self.refresh_all();return
        w=tk.Toplevel(self.root);w.title('Set up super-user' if first_admin else 'Bookstore sign in / registration')
        w.configure(bg=PANEL);w.geometry('550x465');w.resizable(False,False);w.transient(self.root);w.grab_set()
        self._label(w,'FIRST ADMIN SETUP' if first_admin else 'SECURE ACCOUNT ACCESS',fg=GOLD,
                    font=('Segoe UI',18,'bold')).pack(pady=(23,8))
        self._label(w,'Enter an account name and password. Then authenticate with voice or face.',
                    fg=MUTED,wraplength=470).pack(padx=20,pady=(0,18))
        form=self._frame(w);form.pack()
        usr=tk.StringVar();pwd=tk.StringVar();method=tk.StringVar(value='Voice')
        self._label(form,'Username').grid(row=0,column=0,sticky='w',pady=9,padx=10)
        ttk.Entry(form,textvariable=usr,width=33).grid(row=0,column=1,pady=9)
        self._label(form,'Password / PIN').grid(row=1,column=0,sticky='w',pady=9,padx=10)
        ttk.Entry(form,textvariable=pwd,width=33,show='●').grid(row=1,column=1,pady=9)
        self._label(form,'Biometric method').grid(row=2,column=0,sticky='w',pady=9,padx=10)
        ttk.Combobox(form,textvariable=method,values=['Voice','Face'],state='readonly',width=29).grid(row=2,column=1,pady=9)
        feedback=tk.StringVar(value='Voice: speak “'+biometrics.PHRASE+'” 3 times when enrolling.\nFace: press SPACE to capture frames in the camera window.')
        self._label(w,'',fg=MUTED).pack()
        self._label(w,'',fg=MUTED).pack_forget()
        status=self._label(w,'',fg=GOLD,wraplength=470,justify='center')
        status.pack(padx=20,pady=8)
        is_busy=tk.BooleanVar(value=False)
        def work_job(kind):
            if is_busy.get():return
            username=usr.get();pin=pwd.get()
            if not username or not pin:return messagebox.showwarning('Account','Enter username and password.',parent=w)
            user_id=None
            if kind=='register':
                try:user_id=db.create_user(username,pin,'SU' if first_admin else 'RC',trusted=first_admin)
                except Exception as e:return messagebox.showerror('Registration',str(e),parent=w)
            else:
                try:user_id=db.login_pin_check(username,pin)['id']
                except Exception as e:return messagebox.showerror('Sign-in',str(e),parent=w)
            is_busy.set(True)
            register=kind=='register'
            status.config(text='Capturing '+('three voice samples (3s each).' if method.get()=='Voice' and register else
                                   'voice sample (3s).' if method.get()=='Voice' else 'face from camera. Press SPACE to capture; ESC cancels.'))
            for button in (sign,reg):button.config(state='disabled')
            def work():
                try:
                    if method.get()=='Voice':
                        if register:
                            import time
                            vectors=[]
                            for n in range(3):
                                if n:time.sleep(0.8)
                                vectors.append(biometrics.capture_voice())
                            biometrics.enroll_voice(user_id,vectors)
                        else:
                            ok,score=biometrics.verify_voice(user_id,biometrics.capture_voice())
                            if not ok:raise PermissionError(f'Voice did not match (distance {score:.2f}). Retry slowly.')
                    else:
                        captured=biometrics.capture_faces(user_id,enroll=register)
                        if not register:
                            ok,score=biometrics.verify_face(user_id,captured)
                            if not ok:raise PermissionError(f'Face did not match (distance {score:.1f}).')
                    error=None
                except Exception as e:error=str(e)
                def finish():
                    is_busy.set(False)
                    if error:
                        if register:
                            db.delete_unenrolled_user(user_id)
                            if biometrics.face_enrolled(user_id):
                                (biometrics.face_dir()/f'{user_id}.npz').unlink(missing_ok=True)
                        status.config(text='Failed: '+error)
                        for button in (sign,reg):button.config(state='normal')
                        return
                    db.log_event(user_id,'enroll' if register else 'login',method.get())
                    self.user_id=user_id;self.selected_book=None;w.destroy();self.refresh_all()
                    if register:messagebox.showinfo('Account ready','Account created and biometric profile enrolled.')
                self.root.after(0,finish)
            threading.Thread(target=work,daemon=True).start()
        controls=self._frame(w);controls.pack(pady=(8,0))
        sign=ttk.Button(controls,text='Sign in',style='Accent.TButton',command=lambda:work_job('login'))
        reg=ttk.Button(controls,text='Create & enroll',command=lambda:work_job('register'))
        if not first_admin:sign.pack(side='left',padx=9)
        reg.pack(side='left',padx=9)
        self._label(w,'Visitors may browse and review without signing in.',fg=MUTED,font=('Segoe UI',9)).pack(pady=19)

    def refresh_all(self):
        u=self.user
        self.session.config(text=f"{u['username']}  •  {u['role']}" if u else 'Browsing as visitor  •  VS')
        self.login_button.config(text='Log out' if u else 'Sign in / Create account')
        self.category_box['values']=['All']+[r['category'] for r in db.rows('SELECT DISTINCT category FROM books ORDER BY category')]
        self.search_books();self.refresh_home();self.refresh_wallet();self.refresh_admin();self.refresh_journey()
        if self.selected_book:self.refresh_reviews()


def main():
    db.init_db()
    root=tk.Tk()
    BookstoreApp(root)
    root.mainloop()
