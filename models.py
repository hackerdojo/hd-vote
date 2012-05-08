from google.appengine.ext import db
from google.appengine.api import urlfetch, memcache, users, mail
from datetime import datetime, timedelta

import logging


class Issue(db.Model):
	"""Represents a single issue which is being voted on"""
	status = db.StringProperty(required=True, default='active', choices=set(
				['active', 'done', 'canceled']))
	is_public = db.BooleanProperty(default=False) #is issue listed on site or just by sharing url?
	creator = db.UserProperty(auto_current_user=True)
	title = db.StringProperty(required=True)
	description = db.TextProperty()
	duration = db.IntegerProperty()
	creation_date = db.DateTimeProperty(auto_now_add=True)
	start_time = db.DateTimeProperty() #time when first vote is cast
	end_time = db.DateTimeProperty() #time when vote will end
	urlcode = db.StringProperty(required=True)
	
	#Implicit Properties:
	#choices = Implicitly created list of choice objects
	#votes - implicitly created list of vote objects
	
	def add_choice(self,choice_name):
		new_choice = Choice(name=choice_name,issue=self)
		new_choice.put()
		
	def remove_choice(self,choice):
		choice.delete()
	
	def vote_count(self):
		return self.votes.count(999999)
		
	def vote_for_member(self,member=None):
		if not member:
			member = users.get_current_user()
		logging.info('member:%s voted:%s' % (member.nickname(),self.votes.filter('member =',member).fetch(20)))
		return self.votes.filter('member =',member).get()
		
	def register_vote(self,choice,member=None):
		if not member:
			member = users.get_current_user()
		member_vote = self.vote_for_member(member)
		was_changed = False
		if(member_vote):
			member_vote.choice = choice
			was_changed = True
		else:
			member_vote = Vote(member=member,choice=choice,issue=self)
		member_vote.put()
		if(not self.start_time):
			self.start_time = datetime.now()
			self.end_time = self.start_time + timedelta(hours=self.duration)
			self.put()
		return was_changed
		
	def extend_duration(self,hours):
		self.duration += hours
		if self.start_time:
			self.end_time = self.start_time + timedelta(hours=self.duration)
		self.put()
		
	def days_left(self):
		delta = self.end_time - datetime.now()
		return delta.days
		
	def hours_left(self):
		delta = self.end_time - datetime.now()
		#days = delta.days
		#hours = days*24 + delta.seconds/3600
		hours = delta.seconds/3600
		return hours
		
	def is_active(self):
		return self.status in ('active')
		
	def has_results(self):
		return self.status in ('done')
	
	def member_is_creator(self,member=None):
		if not member:
			member = users.get_current_user()
		return member == self.creator
		
	def winning_choices(self):#returns list of keys of winning choices (may be a tie)
		result = []
		high_vote = 0
		for choice in self.choices:
			cnt = choice.vote_count()
			if cnt == high_vote:
				result.append(choice.key())
			elif cnt > high_vote:
				result = [choice.key()]
				high_vote = cnt
		return result
		
	def update_status(self):
		if self.is_active:
			if self.end_time:
				if self.end_time <= datetime.now():
					logging.info('status changed for issue: %s' % (self.title))
					self.status = 'done'
					self.put()
		
	@classmethod
	def issues_created_by(cls, member=None,limit=20):
		if not member:
			member = users.get_current_user()
		return cls.all().filter('creator =',member).order('-creation_date').fetch(limit)
	
	@classmethod
	def issues_voted_on(cls, member=None, limit=20):
		if not member:
			member = users.get_current_user()
		if not member:#if logged out
			return []
		member_votes = Vote.all().filter('member =',member).order('-update_time').fetch(limit)
		##logging.info('member_votes:%s' % (member_votes))
		##logging.info('output:%s' % ([vote.issue for vote in member_votes]))
		return [vote.issue for vote in member_votes]
		
	@classmethod
	def recent_results(cls, member=None,limit=20):#*** Need to fix, limit will be incorrect here because of filtering
		if not member:
			member = users.get_current_user()
		if not member:#if logged out
			return []
		recent = cls.all().filter('status =','done').order('-end_time').fetch(limit)
		return [issue for issue in recent if issue.vote_for_member()] #***this is probably slow
		#member_votes = Vote.all().filter('member =',member).fetch(limit)
		#return [vote.issue for vote in member_votes if vote.issue.has_results()]
			
class Choice(db.Model):
	"""Represents a possible response to an issue (e.g. Yes)"""
	name = db.StringProperty(required=True)
	issue = db.ReferenceProperty(Issue,collection_name='choices')
	#votes - implicitly created list of vote objects
	
	def is_member_vote(self,member=None):
		if not member:
			member = users.get_current_user()
		if self.votes.filter('member =',member).get():
			logging.info("Yup member:%s (%s)" % (member.nickname(),users.get_current_user()))
			return True
		logging.info("Nope")
		return False
		
	def vote_count(self):
		return self.votes.count(999999)
		
	def percentage(self):
		total_votes = float(self.issue.vote_count())
		if(total_votes):
			return round(float(self.vote_count()) / total_votes,3) * 100 #cnt/total
		return 0
	
	def is_winning(self):
		logging.info('%s in result(s) %s: %s',self.name,self.issue.winning_choices()[0].name, self.issue.winning_choices())
		return self.key() in self.issue.winning_choices()


	
	
class Vote(db.Model):
	"""Represents a single vote by a member"""
	member = db.UserProperty(auto_current_user=True)
	choice = db.ReferenceProperty(Choice, collection_name='votes')
	issue = db.ReferenceProperty(Issue,collection_name='votes')
	update_time = db.DateTimeProperty(auto_now=True)
