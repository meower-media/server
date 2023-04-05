import time

from src.common.entities import posts, users
from src.common.util import errors
from src.common.database import db, count_pages


class Report:
	def __init__(
		self,
		_id: str,
		type: int,
		reports: list,
		score: int,
		created: int
	):
		self.id = _id
		self.type = type
		self.reports = reports
		self.score = score
		self.created = created

	@property
	def admin(self):
		data = self.content.public
		data.update({
			"type": self.type,
			"reports": self.reports,
			"score": self.score
		})
		return data

	@property
	def content(self):
		if self.type == 0:
			return posts.get_post(self.id)
		elif self.type == 1:
			return users.get_user(self.id)
		else:
			raise errors.NotFound

	def add_report(self, username: str, user_reputation: float):
		if username not in self.reports:
			self.reports.append(username)
			self.score += user_reputation
			db.reports.update_one({"_id": self.id}, {"$set": {
				"reports": self.reports,
				"score": self.score
			}})

	def close(self, status: bool|None, actor: str = None):
		if status is not None:
			# Construct inbox message
			if status:
				content = "We took action on one of your recent reports against @"
			else:
				content = "We could not take action on one of your recent reports against @"
			if self.type == 0:
				content += f"{self.content.author}'s post."
			elif self.type == 1:
				content += f"{self.content.username}."
			if status:
				content += " Thank you for your help with keeping Meower a safe and welcoming place!"
			else:
				content += " The content you reported was not severe enough to warrant action being taken. We still want to thank you for your help with keeping Meower a safe and welcoming place!"

			# Send inbox messages
			for username in self.reports:
				posts.create_inbox_message(username, content)
			
			# Update report reputation
			db.users.update_many({"_id": {"$in": self.reports}}, {"$inc": {
				"report_reputation": (0.01 if status else -0.01)
			}})

		# Delete report
		db.reports.delete_one({"_id": self.id})


def create_report(content_type: int, content_id: str, username: str, user_reputation: float):
	try:
		report = get_report(content_id)
	except errors.NotFound:
		# Make sure content exists
		if content_type == 0:
			posts.get_post(content_id)
		elif content_type == 1:
			users.get_user(content_id)

		# Create report data
		report_data = {
			"_id": content_id,
			"type": content_type,
			"reports": [username],
			"score": user_reputation,
			"created": int(time.time())
		}

		# Insert report into database
		db.reports.insert_one(report_data)

		# Return report object
		return Report(**report_data)
	else:
		report.add_report(username, user_reputation)
		return report


def close_report(content_id: str, status: bool|None, actor: str = None):
	try:
		report = get_report(content_id)
	except errors.NotFound:
		pass
	else:
		report.close(status, actor)


def get_report(report_id: str):
	# Get report from database
	report_data = db.reports.find_one({"_id": report_id})

	# Return report object
	if report_data:
		return Report(**report_data)
	else:
		raise errors.NotFound


def get_reports(page: int = 1) -> list[Report]:
	return count_pages("reports", {}), [Report(**report) for report in db.reports.find({},
												   sort=[("score", -1)],
												   skip=((page-1)*25),
												   limit=25)]
