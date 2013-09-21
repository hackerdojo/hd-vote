import cgi

import webapp2
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.api import urlfetch, memcache, users, mail
from google.appengine.ext import deferred

import logging, urllib, os, random
from datetime import datetime, timedelta

from models import Issue, Choice, Vote


class MainPage(webapp.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if user:
      logout_url = users.create_logout_url('/')
      issues = Issue.all().order('-creation_date').filter('visibility',"public").fetch(30)
      success_type = self.request.get('success')
      success_msg = None
      if success_type == 'vote':
        success_msg = 'Your vote was successfully cast!'
      if success_type == 'updated':
        success_msg = 'Your vote was successfully updated!'
      #created_by = Issue.issues_created_by(member=user,limit=20)
      #voted_on = Issue.issues_voted_on(member=user,limit=20)
      #recent_results = [issue for issue in voted_on if issue.has_results]
      #recent_voted = [issue for issue in voted_on if issue.is_active()]
      #recent_results = Issue.recent_results(limit=20)
      self.response.out.write(template.render('templates/overview.html', locals()))
    else:
      self.redirect(users.create_login_url('/'))
            
    
class NewHandler(webapp.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if user:
      logout_url = users.create_logout_url('/')
    else:
      self.redirect(users.create_login_url(self.request.uri))
      return
    option_one = "Yes"
    option_two = "No"
    self.response.out.write(template.render('templates/new.html', locals()))

  def post(self):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.uri))
      return
    
    duration_amount = int(self.request.get('duration_amount'))
    multiplier = int(self.request.get('duration_multiplier'))
    visibility = self.request.get('visibility')
    hashcode = random_string()
    title = cgi.escape(self.request.get('title'))
    description = cgi.escape(self.request.get('description'))

    if self.request.get('purchase'):
      title = "Purchase: "+cgi.escape(self.request.get('title'))
      description = "<a href=\""+cgi.escape(self.request.get('url'))+"\">"+cgi.escape(self.request.get('url'))+"</a><br>"+ \
         "<br>Price: $"+cgi.escape(self.request.get('price'))+"<br>"+ \
         "Qty: "+cgi.escape(self.request.get('qty'))+"<br>"+ \
         "Total: $"+cgi.escape(self.request.get('total'))+"<br> "+ \
         "<br>"+cgi.escape(self.request.get('description'))

    issue = Issue(
      visibility = visibility,
      title = title,
      description = description,
      duration = duration_amount * multiplier,
                        urlcode = hashcode)
    issue.put()
    if self.request.get('option1'):
      issue.add_choice(cgi.escape(self.request.get('option1')))
    if self.request.get('option2'):
      issue.add_choice(cgi.escape(self.request.get('option2')))
    if self.request.get('option3'):
      issue.add_choice(cgi.escape(self.request.get('option3')))
    if self.request.get('option4'):
      issue.add_choice(cgi.escape(self.request.get('option4')))
    if self.request.get('option5'):
      issue.add_choice(cgi.escape(self.request.get('option5')))

    if self.request.get('purchase'):
      details = cgi.escape(self.request.get('url'))+"\n\n"+ \
         "Price: $"+cgi.escape(self.request.get('price'))+"\n"+ \
         "Qty: "+cgi.escape(self.request.get('qty'))+"\n"+ \
         "Total: $"+cgi.escape(self.request.get('total'))+"\n\n"+ \
         cgi.escape(self.request.get('description'))
      notify_purchase(details,issue)
      k = issue.key()
      deferred.defer(later_results, k, _countdown=(duration_amount * multiplier*60*60)+30)

    self.redirect('/redirect/%s?success=new' % issue.urlcode)

class PurchaseHandler(webapp.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if user:
      logout_url = users.create_logout_url('/')
    else:
      self.redirect(users.create_login_url(self.request.uri))
      return
    option_one = "Yes, approve purchase"
    option_two = "No, do not approve purchase"
    self.response.out.write(template.render('templates/purchase.html', locals()))

class EditHandler(webapp.RequestHandler):
  def get(self,urlcode):
    user = users.get_current_user()
    if user:
      logout_url = users.create_logout_url('/')
    else:
      self.redirect(users.create_login_url(self.request.uri))
      return
    issue = Issue.get_issue_by_urlcode(urlcode)
    choices = issue.choices
    self.response.out.write(template.render('templates/edit.html', locals()))

  def post(self,urlcode):
    user = users.get_current_user()
    if user:
      logout_url = users.create_logout_url('/')
    else:
      self.redirect(users.create_login_url(self.request.uri))
      return
    issue = Issue.get_issue_by_urlcode(urlcode)

    if self.request.get('extend'):#if extending vote
      choices = issue.choices
      extend_amount = int(self.request.get('extend_amount')) * int(self.request.get('extend_multiplier'))
      issue.extend_duration(extend_amount)
      self.redirect('/redirect/%s?success=extended' % issue.urlcode)
      
    else:#otherwise we are saving changes
      if issue.vote_count():
        raise Exception('Unable to change issue text once votes have been cast')

      duration_amount = int(self.request.get('duration_amount'))
      multiplier = int(self.request.get('duration_multiplier'))
      issue.duration = duration_amount * multiplier
      if self.request.get('title'):
        issue.title = cgi.escape(self.request.get('title'))
      if self.request.get('description'):
        issue.description = cgi.escape(self.request.get('description'))
      if self.request.get('option1') and self.request.get('option2'):
        choices = issue.choices
        db.delete(choices)
        issue.add_choice(cgi.escape(self.request.get('option1')))
        issue.add_choice(cgi.escape(self.request.get('option2')))
        if self.request.get('option3'):
          issue.add_choice(cgi.escape(self.request.get('option3')))
        if self.request.get('option4'):
          issue.add_choice(cgi.escape(self.request.get('option4')))
        if self.request.get('option5'):
          issue.add_choice(cgi.escape(self.request.get('option5')))
      issue.put()
      #choices = issue.choices
      self.redirect('/redirect/%s' % issue.urlcode)
      #self.response.out.write(template.render('templates/edit.html', locals()))
      

class RedirectHandler(webapp.RequestHandler):
  def get(self,issueurl):
    success_type = self.request.get('success')
    success_msg = None
    if success_type == 'extended':
      success_msg = 'Poll duration has been extended!'
    if success_type == 'new':
      success_msg = 'Your poll has been created!'
    if success_type == 'voted':
      success_msg = 'Your vote was successfully cast!'
    if success_type == 'updated':
      success_msg = 'Your vote was successfully updated!'
    user = users.get_current_user()
    host = os.environ['HTTP_HOST']
    self.response.out.write(template.render('templates/redirect.html', locals()))

#class ResultHandler(webapp.RequestHandler):
#  def get(self,urlcode):
#    issue = Issue.get_issue_by_urlcode(urlcode)
#    issue.update_status()
#    yes = 0
#    no = 0
#    for choice in issue.choices:
#      if "Yes" in choice.name:
#        yes = choice.vote_count()
#      if "No" in choice.name:
#        no = choice.vote_count()
#
#    passed = "Not approved"
#    if yes > no:
#      passed = "Purchase Approved"
#
#    issueUrl = self.request.uri
#    self.response.out.write(" Status="+str(issue.status))
#    self.response.out.write(" Yes="+str(yes))
#    self.response.out.write(" No="+str(no))
#    self.response.out.write(" Passed="+str(passed))
#    if "done" in issue.status:
#      notify_results(passed,yes,no,issue)
    
class IssueHandler(webapp.RequestHandler):
  def get(self,urlcode):
    user = users.get_current_user()
    if user:
      logout_url = users.create_logout_url('/')
    else:
      self.redirect(users.create_login_url(self.request.uri))
      return
    
    issue = Issue.get_issue_by_urlcode(urlcode)
    issue.update_status()
    
    #vote = issue.vote_for_member(user)

    issueUrl = self.request.uri
    self.response.out.write(template.render('templates/issue.html', locals()))
    
    
  def post(self,urlcode):
    user = users.get_current_user()
    if user:
      logout_url = users.create_logout_url('/')
    else:
      self.redirect(users.create_login_url(self.request.uri))
    
    issue = Issue.get_issue_by_urlcode(urlcode)
    #vote = issue.vote_for_member()
    
    new_choice = Choice.get_by_id(int(self.request.get('choice')))
    was_updated = issue.register_vote(new_choice)
    self.response.out.write(template.render('templates/issue.html', locals()))
    if was_updated:
      self.redirect('/redirect/%s?success=updated' % issue.urlcode)
    else:
      self.redirect('/redirect/%s?success=voted' % issue.urlcode)


def later_results(k):
    issue = Issue.get(k)
    issue.update_status()
    yes = 0
    no = 0
    for choice in issue.choices:
      if "Yes" in choice.name:
        yes = choice.vote_count()
      if "No" in choice.name:
        no = choice.vote_count()

    passed = "Not approved"
    if yes > no:
      passed = "Purchase Approved"

    notify_results(passed,yes,no,issue)


def notify_results(passed,yes,no,issue):
  body = """
Voting Results: %s

Yes: %s votes
No: %s votes

http://%s/issue/%s

""" % (
    passed,
    yes,
    no,
    os.environ.get('HTTP_HOST'),
    issue.urlcode)

  deferred.defer(mail.send_mail, sender='Voting Robot <robot@hackerdojo.com>', to="brian.klug@hackerdojo.com", cc=issue.creator.nickname()+"@hackerdojo.com",
   subject=issue.title,
   body=body, _queue="emailthrottle")
    
def notify_purchase(details,issue):
  user = users.get_current_user()
  body = """
%s has proposed the following purchase request.  

********************************************************************

%s
%s

********************************************************************

VOTING LINK: http://%s/issue/%s

********************************************************************

Or, discuss the issue on this thread.  Any modifications will
require a new purchase proposal.

http://vote.hackerdojo.com/purchase

""" % (
    user.nickname(),
    issue.title, 
    details,
    os.environ.get('HTTP_HOST'),
    issue.urlcode)

  deferred.defer(mail.send_mail, sender='Voting Robot <robot@hackerdojo.com>', to="brian.klug@hackerdojo.com", cc=user.nickname()+"@hackerdojo.com",
   subject=issue.title,
   body=body, _queue="emailthrottle")

def random_string():
    hashbase = '1234567890abcdefghijklmnopqrstuvwxyz'
    return ''.join(random.sample(hashbase,len(hashbase)))

app = webapp2.WSGIApplication([
    ('/',MainPage),
    ('/new',NewHandler),
    ('/purchase',PurchaseHandler),
    ('/redirect/(\w+).*',RedirectHandler),
    ('/issue/(\w+).*',IssueHandler),
#    ('/result/(\w+).*',ResultHandler),
    ('/edit/(\w+).*',EditHandler)],
    debug=True)


