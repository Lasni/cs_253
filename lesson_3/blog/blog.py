import webapp2
import jinja2
import os
from google.appengine.ext import db
import random
import hashlib
from string import letters
import hmac
import re


# locate the folder where the templates are and assign it to a variable
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
# load said templates and store them in a variable
jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),
                                       autoescape=True)

# secret for hashing
secret = "AfwIghGhaiwhcGHwadlgpehH"


# NEED MORE INFO
def blog_key(name='default'):
    return db.Key.from_path('blog', name)


def render_str(template, **params):
    """ Global function for rendering a template with params.
        Needed for use inside the Post class that doesn't inherit from BlogHandler class.
    """
    t = jinja_environment.get_template(template)
    return t.render(params)


# Returns val and hashed val
def make_secure_val(val):
    return "{}|{}".format(val, hmac.new(secret, val).hexdigest())


# Checks if secure_val's val hashes to secure_val
def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val


""" USER STUFF """


def make_salt(length=5):
    return ''.join(random.choice(letters) for x in range(length))


def make_pw_hash(name, pw, salt=None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '{},{}'.format(salt, h)


def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)


def users_key(group='default'):
    return db.Key.from_path('users', group)


class User(db.Model):
    name = db.StringProperty(required=True)
    pw_hash = db.StringProperty(required=True)
    email = db.StringProperty()

    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid, parent=users_key())

    @classmethod
    def by_name(cls, name):
        u = User.all().filter('name =', name).get()
        return u

    @classmethod
    def register(cls, name, pw, email=None):
        pw_hash = make_pw_hash(name, pw)
        return User(parent=users_key(),
                    name=name,
                    pw_hash=pw_hash,
                    email=email)

    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u


# Main BlogHandler class with methods for rendering the templates with params
class BlogHandler(webapp2.RequestHandler):
    def write(self, *args, **kwargs):
        self.response.out.write(*args, **kwargs)

    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)

    def render(self, template, **kwargs):
        self.write(self.render_str(template, **kwargs))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header('Set-Cookie',
                                         '{}={}; Path=/'.format(name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *args, **kwargs):
        webapp2.RequestHandler.initialize(self, *args, **kwargs)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))


# Post class that stores data queried from the database
class Post(db.Model):
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)

    # Render method that uses the above defined global render_str function
    def render(self):
        # Each time that we render the template with params, we also replace all the newlines in the content with <br>
        self.rerender_text = self.content.replace('\n', '<br>')
        return render_str('post.html', p=self)


# Class that fetches 10 latest blog posts
class BlogFront(BlogHandler):
    def get(self):
        posts = greetings = db.GqlQuery('SELECT * FROM Post ORDER BY created DESC LIMIT 10')
        self.render('front.html', posts=posts)


# Class for fetching the post that corresponds to its post_id
class PostPage(BlogHandler):
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)

        if not post:
            self.error(404)
            return

        self.render('permalink.html', post=post)


# Class that fetches the subject and content data, creates a Post object with it, writes it and redirects to a new page
class NewPost(BlogHandler):
    def get(self):
        if self.user:
            self.render('newpost.html')
        else:
            self.redirect('/login')

    def post(self):
        if not self.user:
            self.redirect('/blog')

        subject = self.request.get('subject')
        content = self.request.get('content')

        if subject and content:
            p = Post(parent=blog_key(), subject=subject, content=content)
            p.put()
            self.redirect('/blog/%s' % str(p.key().id()))
        else:
            error = "Enter the subject and content, please!"
            self.render('newpost.html', subject=subject,
                        content=content, error=error)
