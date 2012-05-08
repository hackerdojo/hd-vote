import cgi
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.api import urlfetch, memcache, users, mail

import logging, urllib, os, random
from datetime import datetime, timedelta

from models import Issue, Choice, Vote


class MainPage(webapp.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			logout_url = users.create_logout_url('/')
		else:
			login_url = users.create_login_url('/')
		issues = Issue.all().order('creation_date').fetch(30)
		success_type = self.request.get('success')
		success_msg = None
		if success_type == 'vote':
			success_msg = 'Your vote was successfully cast!'
		if success_type == 'updated':
			success_msg = 'Your vote was successfully updated!'
		created_by = Issue.issues_created_by(member=user,limit=20)
		voted_on = Issue.issues_voted_on(member=user,limit=20)
		#recent_results = [issue for issue in voted_on if issue.has_results]
		recent_voted = [issue for issue in voted_on if issue.is_active()]
		recent_results = Issue.recent_results(limit=20)
		self.response.out.write(template.render('templates/overview.html', locals()))
				
		
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
		hashcode = random_string()
		issue = Issue(
			title = cgi.escape(self.request.get('title')),
			description = cgi.escape(self.request.get('description')),
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
		
		#self.redirect('/issue/%s' % (issue.key().id()))
		self.redirect('/issue/%s' % issue.urlcode)

class EditHandler(webapp.RequestHandler):
	def get(self,id):
		user = users.get_current_user()
		if user:
			logout_url = users.create_logout_url('/')
		else:
			self.redirect(users.create_login_url(self.request.uri))
			return
		#issue = Issue.get_by_id(int(id))
		issue = Issue.get_by_urlcode(urlcode)
		choices = issue.choices
		self.response.out.write(template.render('templates/edit.html', locals()))

	def post(self,id):
		user = users.get_current_user()
		if user:
			logout_url = users.create_logout_url('/')
		else:
			self.redirect(users.create_login_url(self.request.uri))
			return
		#issue = Issue.get_by_id(int(id))
		issue = Issue.get_by_urlcode(urlcode)
		
		if self.request.get('extend'):#if extending vote
			choices = issue.choices
			extend_amount = int(self.request.get('extend_amount')) * int(self.request.get('extend_multiplier'))
			issue.extend_duration(extend_amount)
			self.response.out.write(template.render('templates/edit.html', locals()))
			
		else:#otherwise we are saving changes
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
			self.redirect('/issue/%s' % issue.urlcode)
			#self.response.out.write(template.render('templates/edit.html', locals()))
			


class IssueHandler(webapp.RequestHandler):
	def get(self,id):
		user = users.get_current_user()
		if user:
			logout_url = users.create_logout_url('/')
		else:
			self.redirect(users.create_login_url(self.request.uri))
			return
		
		#issue = Issue.get_by_id(int(id))
		issue = Issue.get_by_urlcode(urlcode)
		issue.update_status()
		
		vote = issue.vote_for_member(user)

		issueUrl = self.request.uri
		self.response.out.write(template.render('templates/Issue.html', locals()))
		
		
	def post(self,id):
		user = users.get_current_user()
		if not user: #don't want someone who is not authenticated to be able to vote
			self.redirect(users.create_login_url(self.request.uri))
			return
		
		#issue = Issue.get_by_id(int(id))
                issue = Issue.get_by_url(urlcode)
		#vote = issue.vote_for_member()
		
		new_choice = Choice.get_by_id(int(self.request.get('choice')))
		was_updated = issue.register_vote(new_choice)
		
		if was_updated:
			self.redirect('/?success=updated')
		else:
			self.redirect('/?success=vote')
		

def random_string():
    hashbase = 'abcd1234'
    return ''.join(random.sample(hashbase,len(hashbase)))

def main():
	application = webapp.WSGIApplication([
		('/',MainPage),
		('/new',NewHandler),
		('/issue/(\d+).*',IssueHandler),
		('/edit/(\d+).*',EditHandler)],
		debug=True)
	util.run_wsgi_app(application)
	
if __name__ == '__main__':
    main()
