import os
import tempfile
import unittest
from pathlib import Path
import numpy as np
from smartbookstore import database as db, intelligence, biometrics, image_search


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_db=db.DB_FILE
        self.old_data=db.DATA_DIR
        db.DATA_DIR=Path(self.tmp.name)
        db.DB_FILE=db.DATA_DIR/'test.sqlite3'
        db.init_db()
        self.admin=db.create_user('superuser','adminpass','SU',trusted=True)
        self.customer=db.create_user('customer','securepass')

    def tearDown(self):
        db.DB_FILE=self.old_db
        db.DATA_DIR=self.old_data
        self.tmp.cleanup()

    def test_registration_and_login(self):
        self.assertTrue(db.has_admin())
        with self.assertRaises(PermissionError):db.create_user('secondadmin','passwd','SU',trusted=True)
        self.assertEqual(db.login_pin_check('customer','securepass')['id'],self.customer)
        with self.assertRaises(PermissionError):db.login_pin_check('customer','incorrect')

    def test_overdraft_fine_suspension_and_reopen(self):
        b=db.get_book(1)
        outcome=db.purchase(self.customer,b['id'])
        self.assertEqual(outcome['fine_cents'],100)
        self.assertTrue(outcome['suspended'])
        self.assertEqual(outcome['balance_cents'],-b['price_cents']-100)
        with self.assertRaises(PermissionError):db.login_pin_check('customer','securepass')
        with self.assertRaises(PermissionError):db.deposit(self.customer,self.customer,10000)
        with self.assertRaises(ValueError):db.deposit(self.admin,self.customer,100,reopen=True)
        db.deposit(self.admin,self.customer,20000,reopen=True)
        self.assertFalse(db.login_pin_check('customer','securepass')['suspended'])
        self.assertEqual(db.get_book(1)['stock'],b['stock']-1)

    def test_vip_promotion_discount(self):
        db.deposit(self.customer,self.customer,100000)
        for i in range(1,5):db.purchase(self.customer,i)
        self.assertEqual(db.get_user(self.customer)['role'],'VC')
        book=db.get_book(5)
        receipt=db.purchase(self.customer,5)
        self.assertEqual(receipt['charged_cents'],(book['price_cents']*90+50)//100)
        self.assertEqual(receipt['fine_cents'],0)

    def test_spend_200_promotion(self):
        expensive=db.add_book(self.admin,'Big Textbook','Example','Science',2025,20100)
        db.deposit(self.customer,self.customer,40000)
        db.purchase(self.customer,expensive)
        self.assertEqual(db.get_user(self.customer)['role'],'VC')

    def test_taboo_block_and_warnings(self):
        self.assertEqual(db.moderate('Spam and scam plus stupid',["spam","scam","stupid"]),
                         ('**** and **** plus ******',3))
        outcome=db.review(1,5,'spam scam idiot stupid',self.customer)
        self.assertTrue(outcome['blocked'])
        self.assertEqual(db.book_rating(1)[1],0)
        db.review(1,5,'spam spam spam spam',self.customer)
        db.review(1,5,'idiot idiot idiot idiot',self.customer)
        self.assertTrue(db.get_user(self.customer)['suspended'])
        self.assertEqual(db.get_user(self.customer)['warning_count'],3)

    def test_guest_and_superuser_warnings(self):
        out=db.review(1,2,'spam scam idiot stupid',None,'VisitorOne')
        self.assertTrue(out['blocked'])
        self.assertIn('warning 1',out['outcome'])
        self.assertEqual(db.one('SELECT warning_count FROM guest_warnings WHERE guest_name=?',('VisitorOne',))[0],1)
        out2=db.review(1,2,'spam scam idiot stupid',self.admin)
        self.assertIn('Admin warning 1',out2['outcome'])
        self.assertEqual(db.get_user(self.admin)['warning_count'],1)

    def test_vip_demote(self):
        db.deposit(self.customer,self.customer,30000)
        for i in range(1,5):db.purchase(self.customer,i)
        self.assertEqual(db.get_user(self.customer)['role'],'VC')
        out=db.review(1,4,'spam scam idiot stupid',self.customer)
        self.assertTrue(out['blocked'])
        self.assertEqual(db.get_user(self.customer)['role'],'RC')
        self.assertEqual(db.get_user(self.customer)['warning_count'],1)

    def test_rating_weights_and_order_lists(self):
        db.deposit(self.customer,self.customer,10000)
        db.purchase(self.customer,1)
        db.review(1,5,'Great novel',self.customer)
        for i in range(3):db.review(1,1,'Not my type',None,'Guest'+str(i))
        avg,n=db.book_rating(1)
        self.assertEqual(n,4)
        self.assertAlmostEqual(avg,13/5)
        for i in range(4):db.review(2,5,'Wonderful',None,'Reader'+str(i))
        no,to=db.order_lists()
        self.assertIn(2,[book['id'] for book,_,_ in to])
        self.assertNotIn(1,[book['id'] for book,_,_ in no])
        for i in range(4):db.review(3,1,'Not recommended',None,'Reader'+str(i))
        no,to=db.order_lists()
        self.assertIn(3,[book['id'] for book,_,_ in no])

    def test_role_restriction_and_finance(self):
        deny=intelligence.ask('show finance report','VS')
        self.assertIn('ACCESS DENIED',deny)
        allow=intelligence.ask('show finance report','SU')
        self.assertIn('FINANCE',allow)
        self.assertFalse(any('admin/' in str(p) for p,_ in intelligence.allowed_files('VS')))
        self.assertTrue(any('admin/' in str(p) for p,_ in intelligence.allowed_files('SU')))

    def test_rag(self):
        matches=intelligence.retrieve('How does a negative wallet balance suspend my account?','VS')
        self.assertTrue(matches)
        self.assertIn('public/',matches[0][0])
        self.assertTrue(intelligence.ask('How does a negative wallet balance suspend my account?','VS').startswith('[RAG'))

    def test_recommendations_and_image(self):
        self.assertEqual(len(db.recommendations()),3)
        db.record_view(1,self.customer)
        self.assertEqual(len(db.recommendations(self.customer)),3)
        sample=db.ROOT/'sample_images'/'1.png'
        matches=image_search.image_matches(sample)
        self.assertTrue(matches)
        self.assertEqual(matches[0][0],0)
        self.assertEqual(matches[0][1]['id'],1)
        internal=db.ROOT/'sample_images'/'example_internal_figure.png'
        match2=image_search.image_matches(internal)
        self.assertEqual(match2[0][1]['id'],1)

    def test_voice_features(self):
        # Synthetic audio validates feature extraction, not biometric recognition quality.
        fs=16000
        t=np.arange(fs*3)/fs
        wave=(0.15*np.sin(2*np.pi*180*t)+0.065*np.sin(2*np.pi*370*t))*np.hanning(len(t))
        f=biometrics.voice_features(wave)
        self.assertEqual(f.shape,(30,))
        biometrics.enroll_voice(self.customer,[f,f+.01,f-.01])
        ok,score=biometrics.verify_voice(self.customer,f)
        self.assertTrue(ok)
        with self.assertRaises(ValueError):biometrics.voice_features(np.zeros(fs*3))


if __name__=='__main__':
    unittest.main()
