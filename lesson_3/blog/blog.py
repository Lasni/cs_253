import webapp2
import jinja2
import os
from google.appengine.ext import db
import re
from string import letters
from google.appengine.api import memcache
import time
import json
import logging


template_dir = os.path.join(os.path.dirname(__file__), "templates")
jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),
                               autoescape=True)


def blog_key(name="default"):
    return db.Key.from_path("blog", name)


def render_str(template, **params):
    t = jinja_environment.get_template(template)
    return t.render(params)


def render_post(response, post):
    response.out.write('<b>' + post.subject + '</b><br>')
    response.out.write(post.content)


class BlogHandler(webapp2.RequestHandler):
    def write(self, *args, **kwargs):
        self.response.out.write(*args, **kwargs)

    def render_str(self, template, **params):
        t = jinja_environment.get_template(template)
        return t.render(params)

    def render(self, template, **kwargs):
        self.write(self.render_str(template, **kwargs))


class BlogPost(db.Model):
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)

    def render(self):
        self.rerender_text = self.content.replace("\n", "<br>")
        return render_str("blog_post.html", p=self)


class BlogFront(BlogHandler):
    def get(self):
        posts = db.GqlQuery("SELECT * FROM BlogPost ORDER BY created DESC LIMIT 10")
        self.render("blog_front.html", posts=posts)


class PostPage(BlogHandler):
    def get(self, post_id):
        key = db.Key.from_path("BlogPost", int(post_id), parent=blog_key())
        post = db.get(key)

        if not post:
            self.error(404)
            return
        else:
            self.render("blog_permalink.html", post=post)


class NewPost(BlogHandler):
    def get(self):
        self.render("blog_newpost.html")

    def post(self):
        subject = self.request.get("subject")
        content = self.request.get("content")

        if subject and content:
            p = BlogPost(parent=blog_key(), subject=subject, content=content)
            p.put()
            x = str(p.key().id())
            self.redirect("/blog/%s" % x)
        else:
            error = "Enter the subject and content, please!"
            self.render("blog_newpost.html", subject=subject,
                        content=content, error=error)