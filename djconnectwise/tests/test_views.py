from django.test import RequestFactory

from test_plus.test import TestCase


class TestBoardListView(TestCase):

    def test_user_must_be_authenticated(self):
        self.assertLoginRequired('cw:board-list-view')

    def test_authenticated_user_can_view_page(self):
        user1 = self.make_user('u1')
        
        with self.login(username=user1.username, password='password'):
            self.get_check_200('cw:board-list-view')
       

