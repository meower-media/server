from quart import Blueprint, current_app as app, request, abort
from pydantic import BaseModel, Field
from typing import Optional, Literal
from base64 import b64decode
import time
import pymongo
import os

from security import DEFAULT_USER_SETTINGS, UserFlags, Permissions


admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


class UpdateReportBody(BaseModel):
    status: Literal["pending", "escalated", "no_action_taken", "action_taken"]

    class Config:
        validate_assignment = True


class UpdateNotesBody(BaseModel):
    notes: str

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


class UpdateUserBanBody(BaseModel):
    state: Literal["none", "temp_restriction", "perm_restriction", "temp_ban", "perm_ban"]
    restrictions: int
    expires: int
    reason: str

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


class UpdateUserBody(BaseModel):
    permissions: Optional[int] = Field(default=None, ge=0)

    class Config:
        validate_assignment = True


class InboxMessageBody(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000
    )

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


class NetblockBody(BaseModel):
    type: int = Field(ge=0, le=1)
    notes: str
    expires: Optional[int] = Field(default=None, ge=0)

    class Config:
        validate_assignment = True


@admin_bp.before_request
async def check_admin_perms():
    if request.method != "OPTIONS":
        if (not request.user) or (not request.permissions):
            abort(401)


@admin_bp.get("/reports")
async def get_reports():
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.VIEW_REPORTS):
        abort(403)

    # Construct query
    query = {}
    sort = [("time", pymongo.DESCENDING)]
    if "status" in request.args:
        query["status"] = request.args["status"]
        if query["status"] == "pending" or query["status"] == "escalated":
            sort = [("score", pymongo.DESCENDING)]
    if "type" in request.args:
        query["type"] = request.args["type"]

    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Get reports
    reports = list(app.files.db.reports.find(query, projection={"reports.ip": 0}, sort=sort, skip=(page-1)*25, limit=25))

    # Get content
    for report in reports:
        if report["type"] == "post":
            report["content"] = app.files.db.posts.find_one({"_id": report.pop("content_id")})
        elif report["type"] == "user":
            report["content"] = app.security.get_account(report.get("content_id"))

    # Add log
    app.security.add_audit_log("got_reports", request.user, request.ip, {
        "status": request.args.get("status", "all"),
        "type": request.args.get("type", "all"),
        "page": page
    })

    # Return reports
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("reports", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = reports
    else:
        payload["index"] = [report["_id"] for report in reports]
    return payload, 200


@admin_bp.get("/reports/<report_id>")
async def get_report(report_id):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.VIEW_REPORTS):
        abort(403)

    # Get report
    report = app.files.db.reports.find_one({"_id": report_id}, projection={"reports.ip": 0})
    if not report:
        abort(404)

    # Get content
    if report["type"] == "post":
        report["content"] = app.files.db.posts.find_one({"_id": report.pop("content_id")})
    elif report["type"] == "user":
        report["content"] = app.security.get_account(report.get("content_id"))

    # Add log
    app.security.add_audit_log("got_report", request.user, request.ip, {"report_id": report_id})

    # Return report
    report["error"] = False
    return report, 200


@admin_bp.patch("/reports/<report_id>")
async def update_report(report_id):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.VIEW_REPORTS):
        abort(403)

    # Get body
    try:
        body = UpdateReportBody(**await request.json)
    except: abort(400)

    # Get report
    report = app.files.db.reports.find_one({"_id": report_id}, projection={"reports.ip": 0})
    if not report:
        abort(404)

    # Update report
    report["status"] = body.status
    app.files.db.reports.update_one({"_id": report_id}, {"$set": {"status": body.status}})

    # Get content
    if report["type"] == "post":
        report["content"] = app.files.db.posts.find_one({"_id": report.pop("content_id")})
    elif report["type"] == "user":
        report["content"] = app.security.get_account(report.get("content_id"))

    # Add log
    app.security.add_audit_log("updated_report", request.user, request.ip, {
        "report_id": report_id, "status": body.status
    })

    # Return report
    report["error"] = False
    return report, 200


@admin_bp.get("/notes/<identifier>")
async def get_admin_notes(identifier):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.VIEW_NOTES):
        abort(403)

    # Get notes
    notes = app.files.db.admin_notes.find_one({"_id": identifier})

    # Add log
    app.security.add_audit_log("got_notes", request.user, request.ip, {"identifier": identifier})

    # Return notes
    if notes:
        notes["error"] = False
        return notes, 200
    else:
        return {
            "_id": identifier,
            "notes": "",
            "last_modified_by": None,
            "last_modified_at": None,
            "error": False
        }, 200


@admin_bp.put("/notes/<identifier>")
async def edit_admin_note(identifier):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.EDIT_NOTES):
        abort(403)

    # Get body
    try:
        body = UpdateNotesBody(**await request.json)
    except: abort(400)

    # Update notes
    notes = {
        "_id": identifier,
        "notes": body.notes,
        "last_modified_by": request.user,
        "last_modified_at": int(time.time())
    }
    app.files.db.admin_notes.update_one({"_id": identifier}, {"$set": notes}, upsert=True)

    # Add log
    app.security.add_audit_log("updated_notes", request.user, request.ip, {"identifier": identifier, "notes": body.notes})

    # Return new notes
    notes["error"] = False
    return notes, 200


@admin_bp.get("/users/<username>")
async def get_user(username):
    # Get account    
    account = app.files.db.usersv0.find_one({"lower_username": username.lower()})
    if not account:
        abort(404)
    
    # Construct payload
    payload = {
        "_id": account["_id"],
        "created": account["created"],
        "uuid": account["uuid"],
        "pfp_data": account["pfp_data"],
        "quote": account["quote"],
        "flags": account["flags"],
        "permissions": account["permissions"],
        "last_seen": account["last_seen"],
        "delete_after": account["delete_after"]
    }

    if not ((account["flags"] & UserFlags.SYSTEM) == UserFlags.SYSTEM or (account["flags"] & UserFlags.DELETED) == UserFlags.DELETED):
        # Add user settings or unread inbox state
        if app.security.has_permission(request.permissions, Permissions.SYSADMIN):
            payload.update({"settings": DEFAULT_USER_SETTINGS})
            user_settings = app.files.db.user_settings.find_one({"_id": username})
            if user_settings:
                del user_settings["_id"]
                payload["settings"].update(user_settings)
        elif app.security.has_permission(request.permissions, Permissions.VIEW_POSTS):
            payload.update({"settings": {"unread_inbox": DEFAULT_USER_SETTINGS}})
            user_settings = app.files.db.user_settings.find_one({"_id": username}, projection={"unread_inbox": 1})
            if user_settings:
                del user_settings["_id"]
                payload["settings"].update(user_settings)

        # Add ban state
        if app.security.has_permission(request.permissions, Permissions.VIEW_BAN_STATES):
            payload["ban"] = account["ban"]

        # Add alts and recent IPs
        if app.security.has_permission(request.permissions, Permissions.VIEW_ALTS):
            # Get netlogs
            netlogs = [{
                "ip": netlog["_id"]["ip"],
                "user": netlog["_id"]["user"],
                "last_used": netlog["last_used"]
            } for netlog in app.files.db.netlog.find({"_id.user": username}, sort=[("last_used", pymongo.DESCENDING)])]

            # Get alts
            alts = [netlog["_id"]["user"] for netlog in app.files.db.netlog.find({"_id.ip": {"$in": [netlog["ip"] for netlog in netlogs]}})]
            if username in alts:
                alts.remove(username)
            payload["alts"] = list(set(alts))

            # Get recent IP info
            if app.security.has_permission(request.permissions, Permissions.VIEW_IPS):
                payload["recent_ips"] = [{
                    "netinfo": app.security.get_netinfo(netlog["ip"]),
                    "last_used": netlog["last_used"],
                    "blocked": (app.supporter.blocked_ips.search_best(netlog["ip"]) is not None),
                    "registration_blocked": (app.supporter.registration_blocked_ips.search_best(netlog["ip"]) is not None)
                } for netlog in netlogs]
    
    # Add log
    app.security.add_audit_log("got_user", request.user, request.ip, {"username": username, "returned_fields": list(payload.keys())})

    payload["error"] = False
    return payload, 200


@admin_bp.patch('/users/<username>')
async def update_user(username):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        abort(403)

    # Get body
    try:
        body = UpdateUserBody(**await request.json)
    except: abort(400)

    # Make sure user exists
    if not app.security.account_exists(username):
        abort(404)

    # Permissions
    if body.permissions is not None:
        # Update user
        app.files.db.usersv0.update_one({"_id": username}, {"$set": {"permissions": body.permissions}})

        # Add log
        app.security.add_audit_log("updated_permissions", request.user, request.ip, {"username": username, "permissions": body.permissions})

        # Sync config between sessions
        app.supporter.sendPacket({"cmd": "direct", "val": {
            "mode": "update_config",
            "payload": {
                "permissions": body.permissions
            }
        }, "id": username})

    return {"error": False}, 200


@admin_bp.delete('/users/<username>')
async def delete_user(username):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.DELETE_USERS):
        abort(403)

    # Make sure user exists
    if not app.security.account_exists(username):
        abort(404)

    # Make sure user isn't protected
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        account = app.files.db.usersv0.find_one({"_id": username}, projection={"flags": 1})
        if (account["flags"] & UserFlags.PROTECTED) == UserFlags.PROTECTED:
            abort(403)

    # Get deletion mode
    deletion_mode = request.args.get("mode")

    # Delete account (or not, depending on the mode)
    if deletion_mode == "cancel":
        app.files.db.usersv0.update_one({"_id": username}, {"$set": {"delete_after": None}})
    elif deletion_mode == "schedule":
        app.files.db.usersv0.update_one({"_id": username}, {"$set": {
            "tokens": [],
            "delete_after": int(time.time())+604800  # 7 days
        }})
        app.supporter.kickUser(username, "LoggedOut")
    elif deletion_mode == "immediate":
        app.security.delete_account(username)
    elif deletion_mode == "purge":
        app.security.delete_account(username, purge=True)
    else:
        abort(400)

    return {"error": False}, 200


@admin_bp.post('/users/<username>/ban')
async def ban_user(username):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.EDIT_BAN_STATES):
        abort(403)

    # Get body
    try:
        body = UpdateUserBanBody(**await request.json)
    except: abort(400)

    # Make sure user exists
    if not app.security.account_exists(username):
        abort(404)

    # Make sure user isn't protected
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        account = app.files.db.usersv0.find_one({"_id": username}, projection={"flags": 1})
        if (account["flags"] & UserFlags.PROTECTED) == UserFlags.PROTECTED:
            abort(403)

    # Update user
    app.files.db.usersv0.update_one({"_id": username}, {"$set": {"ban": body.model_dump()}})

    # Add log
    app.security.add_audit_log("banned", request.user, request.ip, {"username": username, "ban": body.model_dump()})

    # Kick client or send updated ban state
    if (body.state == "perm_ban") or (body.state == "temp_ban" and body.expires > time.time()):
        app.supporter.kickUser(username, status="Banned")
    else:
        app.supporter.sendPacket({"cmd": "direct", "val": {
            "mode": "update_config",
            "payload": {"ban": body.model_dump()},
        }, "id": username})

    return {"error": False}, 200


@admin_bp.get('/users/<username>/posts/<post_origin>')
async def get_user_posts(username, post_origin):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.VIEW_POSTS):
        abort(401)

    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Get posts
    if post_origin == "all":
        query = {"u": username}
    else:
        query = {
            "post_origin": post_origin,
            "$or": [{"isDeleted": False}, {"isDeleted": True}],
            "u": username
        }
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Add log
    app.security.add_audit_log("got_user_posts", request.user, request.ip, {
        "username": username,
        "post_origin": post_origin,
        "page": page
    })

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("posts", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@admin_bp.delete('/users/<username>/posts/<post_origin>')
async def clear_user_posts(username, post_origin):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.EDIT_POSTS):
        abort(401)

    # Make sure user isn't protected
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        account = app.files.db.usersv0.find_one({"_id": username}, projection={"flags": 1})
        if account and (account["flags"] & UserFlags.PROTECTED) == UserFlags.PROTECTED:
            abort(403)

    # Delete posts
    if post_origin == "all":
        query = {"u": username, "isDeleted": False}
    else:
        query = {
            "post_origin": post_origin,
            "isDeleted": False,
            "u": username
        }
    app.files.db.posts.update_many(query, {"$set": {
        "isDeleted": True,
        "mod_deleted": True,
        "deleted_at": int(time.time())
    }})

    # Add log
    app.security.add_audit_log("clear_user_posts", request.user, request.ip, {
        "username": username,
        "post_origin": post_origin
    })

    return {"error": False}, 200


@admin_bp.post('/users/<username>/inbox')
async def send_alert(username):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.SEND_ALERTS):
        abort(401)

    # Get body
    try:
        body = InboxMessageBody(**await request.json)
    except: abort(400)

    # Make sure user exists
    if not app.security.account_exists(username):
        abort(404)

    # Create inbox message
    app.supporter.createPost("inbox", username, body.content)

    # Add log
    app.security.add_audit_log("alerted", request.user, request.ip, {"username": username, "content": body.content})

    return {"error": False}, 200


@admin_bp.post('/users/<username>/kick')
async def kick_user(username):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.KICK_USERS):
        abort(401)
    
    # Check whether to do a force kick
    if request.args.get("force"):
        force = True
    else:
        force = False

    # Kick user
    if force:
        # Forcibly kill all locked out/bugged sessions under that username - This is for extreme cases of account lockup only!
        if not app.cl._get_obj_of_username(username):
            # if the username is stuck in memory, delete it
            if username in app.cl.statedata["ulist"]["usernames"]: 
                del app.cl.statedata["ulist"]["usernames"][username]
                app.cl._send_to_all({"cmd": "ulist", "val": app.cl._get_ulist()})
        
        # Why do I hear boss music?
        else:
            for session in app.cl._get_obj_of_username(username):
                app.log("Forcing killing session {0}".format(session['id']))
                try:
                    # Attempt to disconnect session - Most of the time this will result in a broken pipe error
                    app.cl.kickClient(session)
                except Exception as e:
                    app.log("Session {0} force kill exception: {1} (If this is a BrokenPipe error, this is expected to occur)".format(session['id'], e))

                try:
                    # If it is a broken pipe, forcibly free the session from memory
                    app.cl._closed_connection_server(session, app.cl)
                except Exception as e:
                    app.log("Session {0} force kill exception: {1}".format(session['id'], e))
    else:
        app.files.db.usersv0.update_one({"_id": username}, {"$set": {"tokens": []}})
        app.supporter.kickUser(username)

    # Add log
    app.security.add_audit_log("kicked", request.user, request.ip, {"username": username, "forced": force})

    return {"error": False}, 200


@admin_bp.delete('/users/<username>/quote')
async def clear_quote(username):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.CLEAR_USER_QUOTES):
        abort(401)

    # Make sure user isn't protected
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        account = app.files.db.usersv0.find_one({"_id": username}, projection={"flags": 1})
        if account and (account["flags"] & UserFlags.PROTECTED) == UserFlags.PROTECTED:
            abort(403)

    # Update user
    app.files.db.usersv0.update_one({"_id": username, "quote": {"$ne": None}}, {"$set": {"quote": ""}})

    # Sync config between sessions
    app.supporter.sendPacket({"cmd": "direct", "val": {
        "mode": "update_config",
        "payload": {
            "quote": ""
        }
    }, "id": username})

    # Add log
    app.security.add_audit_log("cleared_quote", request.user, request.ip, {"username": username})

    return {"error": False}, 200


@admin_bp.get('/netinfo/<ip>')
async def get_netinfo(ip):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.VIEW_IPS):
        abort(401)

    # Get netinfo
    netinfo = app.security.get_netinfo(ip)

    # Get netblocks
    netblocks = []
    for radix_node in app.supporter.blocked_ips.search_covering(ip):
        netblocks.append(app.files.db.netblock.find_one({"_id": radix_node.prefix}))
    for radix_node in app.supporter.registration_blocked_ips.search_covering(ip):
        netblocks.append(app.files.db.netblock.find_one({"_id": radix_node.prefix}))

    # Get netlogs
    netlogs = [{
        "ip": netlog["_id"]["ip"],
        "user": netlog["_id"]["user"],
        "last_used": netlog["last_used"]
    } for netlog in app.files.db.netlog.find({"_id.ip": ip}, sort=[("last_used", pymongo.DESCENDING)])]

    # Add log
    app.security.add_audit_log("got_netinfo", request.user, request.ip, {"ip": ip})

    # Return netinfo, netblocks, and netlogs
    return {
        "error": False,
        "netinfo": netinfo,
        "netblocks": netblocks,
        "netlogs": netlogs
    }, 200


@admin_bp.get('/netblocks/<cidr>')
async def get_netblock(cidr):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.VIEW_IPS):
        abort(401)

    # b64 decode CIDR
    cidr = b64decode(cidr.encode()).decode()

    # Get netblock
    netblock = app.files.db.netblock.find_one({"_id": cidr})
    if not netblock:
        abort(404)

    # Add log
    app.security.add_audit_log("got_netblock", request.user, request.ip, {"cidr": cidr, "netblock": netblock})

    # Return netblock
    netblock["error"] = False
    return netblock, 200


@admin_bp.put('/netblocks/<cidr>')
async def create_netblock(cidr):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.BLOCK_IPS):
        abort(401)

    # b64 decode CIDR
    cidr = b64decode(cidr.encode()).decode()

    # Get body
    try:
        body = NetblockBody(**await request.json)
    except: abort(400)

    # Construct netblock obj
    netblock = {
        "_id": cidr,
        "type": body.type,
        "notes": body.notes,
        "created": int(time.time()),
        "expires": body.expires
    }

    # Remove from Radix
    if app.supporter.blocked_ips.search_exact(cidr):
        app.supporter.blocked_ips.delete(cidr)
    if app.supporter.registration_blocked_ips.search_exact(cidr):
        app.supporter.registration_blocked_ips.delete(cidr)

    # Add to Radix
    if body.type == 0:
        app.supporter.blocked_ips.add(cidr)
    elif body.type == 1:
        app.supporter.registration_blocked_ips.add(cidr)

    # Add netblock to database
    app.files.db.netblock.update_one({"_id": cidr}, {"$set": netblock}, upsert=True)

    # Kick clients
    if body.type == 0:
        for client in app.cl.wss.clients:
            if app.supporter.blocked_ips.search_best(app.cl.getIPofObject(client)):
                try:
                    app.cl.kickClient(client)
                except Exception as e:
                    app.log(f"Failed to kick {client}: {e}")

    # Add log
    app.security.add_audit_log("created_netblock", request.user, request.ip, {"cidr": cidr, "netblock": netblock})

    # Return netblock
    netblock["error"] = False
    return netblock, 200


@admin_bp.delete('/netblocks/<cidr>')
async def delete_netblock(cidr):
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.BLOCK_IPS):
        abort(401)

    # b64 decode CIDR
    cidr = b64decode(cidr.encode()).decode()

    # Remove from database
    app.files.db.netblock.delete_one({"_id": cidr})

    # Remove from Radix
    if app.supporter.blocked_ips.search_exact(cidr):
        app.supporter.blocked_ips.delete(cidr)
    if app.supporter.registration_blocked_ips.search_exact(cidr):
        app.supporter.registration_blocked_ips.delete(cidr)

    # Add log
    app.security.add_audit_log("deleted_netblock", request.user, request.ip, {"cidr": cidr})

    return {"error": False}, 200


@admin_bp.get('/announcements')
async def get_announcements():
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.VIEW_POSTS):
        abort(401)

    # Get page
    page = 1
    try:
        page = int(request.args["page"])
    except: pass

    # Get posts
    query = {"post_origin": "inbox", "$or": [{"isDeleted": False}, {"isDeleted": True}], "u": "Server"}
    posts = list(app.files.db.posts.find(query, sort=[("t.e", pymongo.DESCENDING)], skip=(page-1)*25, limit=25))

    # Add log
    app.security.add_audit_log("got_announcements", request.user, request.ip, {"page": page})

    # Return posts
    payload = {
        "error": False,
        "page#": page,
        "pages": app.files.get_total_pages("posts", query)
    }
    if "autoget" in request.args:
        payload["autoget"] = posts
    else:
        payload["index"] = [post["_id"] for post in posts]
    return payload, 200


@admin_bp.post('/announcements')
async def send_announcement():
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.SEND_ANNOUNCEMENTS):
        abort(401)

    # Get body
    try:
        body = InboxMessageBody(**await request.json)
    except: abort(400)

    # Create announcement
    app.supporter.createPost("inbox", "Server", body.content)

    # Add log
    app.security.add_audit_log("sent_announcement", request.user, request.ip, {"content": body.content})

    return {"error": False}, 200


@admin_bp.post('/server/kick-all')
async def kick_all_clients():
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        abort(401)

    # Kick all clients
    app.log("Kicking all clients")
    for client in app.cl.wss.clients:
        try:
            app.cl.kickClient(client)
        except Exception as e:
            app.log(f"Failed to kick {client}: {e}")

    # Add log
    app.security.add_audit_log("kicked_all", request.user, request.ip, {})

    return {"error": False}, 200


@admin_bp.post('/server/restart')
async def restart_server():
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        abort(401)

    # Make sure the server can be restarted
    if not os.getenv("RESET_SCRIPT"):
        abort(404)

    # Add log
    app.security.add_audit_log("restarted_server", request.user, request.ip, {})

    # Restart the server
    app.log("Restarting server")
    os.system(os.getenv("RESET_SCRIPT"))

    return {"error": False}, 200


@admin_bp.post('/server/enable-repair-mode')
async def enable_repair_mode():
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        abort(401)

    # Update database item
    app.files.db.config.update_one({"_id": "status"}, {"$set": {"repair_mode": True}})

    # Update supporter attribute
    app.supporter.repair_mode = True

    # Kick all clients
    app.log("Kicking all clients")
    for client in app.cl.wss.clients:
        try:
            app.cl.kickClient(client)
        except Exception as e:
            app.log(f"Failed to kick {client}: {e}")

    # Add log
    app.security.add_audit_log("enabled_repair_mode", request.user, request.ip, {})

    return {"error": False}, 200


@admin_bp.post('/server/registration/disable')
async def disable_registration():
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        abort(401)

    # Update database item
    app.files.db.config.update_one({"_id": "status"}, {"$set": {"registration": False}})

    # Update supporter attribute
    app.supporter.registration = False

    # Add log
    app.security.add_audit_log("disabled_registration", request.user, request.ip, {})

    return {"error": False}, 200


@admin_bp.post('/server/registration/enable')
async def enable_registration():
    # Check permissions
    if not app.security.has_permission(request.permissions, Permissions.SYSADMIN):
        abort(401)

    # Update database item
    app.files.db.config.update_one({"_id": "status"}, {"$set": {"registration": True}})

    # Update supporter attribute
    app.supporter.registration = True

    # Add log
    app.security.add_audit_log("enabled_registration", request.user, request.ip, {})

    return {"error": False}, 200
