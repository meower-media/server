from flask import Blueprint

router = Blueprint("errors_router", __name__)

@router.errorhandler(400) # Bad request
async def page_not_found(e):
	return {"error": True, "type": "badRequest"}, 400

@router.errorhandler(401) # Unauthorized
async def page_not_found(e):
	return {"error": True, "type": "Unauthorized"}, 401

@router.errorhandler(403) # Forbidden
async def page_not_found(e):
	return {"error": True, "type": "Forbidden"}, 403

@router.errorhandler(404) # We do need a 404 handler.
async def page_not_found(e):
	return {"error": True, "type": "notFound"}, 404

@router.errorhandler(405) # Method not allowed
async def not_allowed(e):
	return {"error": True, "type": "methodNotAllowed"}, 405

@router.errorhandler(500) # Internal
async def internal(e):
	return {"error": True, "type": "Internal"}, 500

@router.errorhandler(503) # CL Reject Mode
async def internal(e):
	return {"error": True, "type": "repairMode"}, 503
