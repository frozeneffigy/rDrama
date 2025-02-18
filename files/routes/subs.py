from files.__main__ import app, limiter, mail
from files.helpers.alerts import *
from files.helpers.wrappers import *
from files.helpers.get import *
from files.helpers.regex import *
from files.classes import *
from .front import frontlist
import tldextract

@app.post("/exile/post/<pid>")
@is_not_permabanned
def exile_post(v, pid):
	try: pid = int(pid)
	except: abort(400)

	p = get_post(pid)
	sub = p.sub
	if not sub: abort(400)

	if sub == 'braincels': abort(403)

	if not v.mods(sub): abort(403)

	u = p.author

	if u.mods(sub): abort(403)

	if u.admin_level < 2 and not u.exiled_from(sub):
		exile = Exile(user_id=u.id, sub=sub, exiler_id=v.id)
		g.db.add(exile)

		send_notification(u.id, f"@{v.username} has exiled you from /h/{sub} for [{p.title}]({p.shortlink})")

	
	return {"message": "User exiled successfully!"}



@app.post("/exile/comment/<cid>")
@is_not_permabanned
def exile_comment(v, cid):
	try: cid = int(cid)
	except: abort(400)

	c = get_comment(cid)
	sub = c.post.sub
	if not sub: abort(400)

	if sub == 'braincels': abort(403)

	if not v.mods(sub): abort(403)

	u = c.author

	if u.mods(sub): abort(403)

	if u.admin_level < 2 and not u.exiled_from(sub):
		exile = Exile(user_id=u.id, sub=sub, exiler_id=v.id)
		g.db.add(exile)

		send_notification(u.id, f"@{v.username} has exiled you from /h/{sub} for [{c.permalink}]({c.shortlink})")

	
	return {"message": "User exiled successfully!"}


@app.post("/h/<sub>/unexile/<uid>")
@is_not_permabanned
def unexile(v, sub, uid):
	u = get_account(uid)

	if not v.mods(sub): abort(403)

	if u.exiled_from(sub):
		exile = g.db.query(Exile).filter_by(user_id=u.id, sub=sub).one_or_none()
		g.db.delete(exile)

		send_notification(u.id, f"@{v.username} has revoked your exile from /h/{sub}")

	
	
	if request.headers.get("Authorization") or request.headers.get("xhr"): return {"message": "User unexiled successfully!"}
	return redirect(f'/h/{sub}/exilees')







@app.post("/h/<sub>/block")
@auth_required
def block_sub(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)
	sub = sub.name

	if v.mods(sub): return {"error": "You can't block subs you mod!"}

	existing = g.db.query(SubBlock).filter_by(user_id=v.id, sub=sub).one_or_none()

	if not existing:
		block = SubBlock(user_id=v.id, sub=sub)
		g.db.add(block)
		cache.delete_memoized(frontlist)

	return {"message": "Sub blocked successfully!"}


@app.post("/h/<sub>/unblock")
@auth_required
def unblock_sub(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)
	sub = sub.name

	block = g.db.query(SubBlock).filter_by(user_id=v.id, sub=sub).one_or_none()

	if block:
		g.db.delete(block)
		cache.delete_memoized(frontlist)

	return {"message": "Sub unblocked successfully!"}

@app.post("/h/<sub>/follow")
@auth_required
def follow_sub(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)

	existing = g.db.query(SubSubscription) \
		.filter_by(user_id=v.id, sub=sub.name).one_or_none()
	if not existing:
		subscription = SubSubscription(user_id=v.id, sub=sub.name)
		g.db.add(subscription)

	return {"message": "Sub followed successfully!"}

@app.post("/h/<sub>/unfollow")
@auth_required
def unfollow_sub(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)

	subscription = g.db.query(SubSubscription) \
		.filter_by(user_id=v.id, sub=sub.name).one_or_none()
	if subscription:
		g.db.delete(subscription)

	return {"message": "Sub unfollowed successfully!"}

@app.get("/h/<sub>/mods")
@auth_required
def mods(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)

	users = g.db.query(User, Mod).join(Mod, Mod.user_id==User.id).filter_by(sub=sub.name).order_by(Mod.created_utc).all()

	return render_template("sub/mods.html", v=v, sub=sub, users=users)


@app.get("/h/<sub>/exilees")
@auth_required
def sub_exilees(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)

	users = g.db.query(User, Exile).join(Exile, Exile.user_id==User.id).filter_by(sub=sub.name).all()

	return render_template("sub/exilees.html", v=v, sub=sub, users=users)


@app.get("/h/<sub>/blockers")
@auth_required
def sub_blockers(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)

	users = g.db.query(User).join(SubBlock, SubBlock.user_id==User.id).filter_by(sub=sub.name).all()

	return render_template("sub/blockers.html", 
		v=v, sub=sub, users=users, verb="blocking")

@app.get("/h/<sub>/followers")
@auth_required
def sub_followers(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)

	users = g.db.query(User) \
			.join(SubSubscription, SubSubscription.user_id==User.id) \
			.filter_by(sub=sub.name).all()

	return render_template("sub/blockers.html", 
		v=v, sub=sub, users=users, verb="following")


@app.post("/h/<sub>/add_mod")
@limiter.limit("1/second;5/day")
@limiter.limit("1/second;5/day", key_func=lambda:f'{request.host}-{session.get("lo_user")}')
@is_not_permabanned
def add_mod(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)
	sub = sub.name

	if not v.mods(sub): abort(403)

	user = request.values.get('user')

	if not user: abort(400)

	user = get_user(user)

	existing = g.db.query(Mod).filter_by(user_id=user.id, sub=sub).one_or_none()

	if not existing:
		mod = Mod(user_id=user.id, sub=sub)
		g.db.add(mod)

		if v.id != user.id:
			send_repeatable_notification(user.id, f"@{v.username} has added you as a mod to /h/{sub}")

	
	return redirect(f'/h/{sub}/mods')


@app.post("/h/<sub>/remove_mod")
@is_not_permabanned
def remove_mod(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)
	sub = sub.name

	if not v.mods(sub): abort(403)

	uid = request.values.get('uid')

	if not uid: abort(400)

	try: uid = int(uid)
	except: abort(400)

	user = get_account(uid)

	if not user: abort(404)

	mod = g.db.query(Mod).filter_by(user_id=user.id, sub=sub).one_or_none()
	if not mod: abort(400)

	if not (v.id == user.id or v.mod_date(sub) and v.mod_date(sub) < mod.created_utc): abort(403)

	g.db.delete(mod)

	if v.id != user.id:
		send_repeatable_notification(user.id, f"@{v.username} has removed you as a mod from /h/{sub}")

	
	return redirect(f'/h/{sub}/mods')

@app.get("/create_hole")
@is_not_permabanned
def create_sub(v):
	if not v.can_create_hole:
		abort(403)

	return render_template("sub/create_hole.html", v=v, cost=HOLE_COST)

@app.post("/create_hole")
@is_not_permabanned
def create_sub2(v):
	if not v.can_create_hole:
		abort(403)

	name = request.values.get('name')
	if not name: abort(400)
	name = name.strip().lower()

	if not valid_sub_regex.fullmatch(name):
		return render_template("sub/create_hole.html", v=v, cost=HOLE_COST, error="Sub name not allowed."), 400

	sub = g.db.query(Sub).filter_by(name=name).one_or_none()
	if not sub:
		if v.coins < HOLE_COST:
			return render_template("sub/create_hole.html", v=v, cost=HOLE_COST, error="You don't have enough coins!"), 403

		v.coins -= HOLE_COST

		g.db.add(v)

		sub = Sub(name=name)
		g.db.add(sub)
		g.db.flush()
		mod = Mod(user_id=v.id, sub=sub.name)
		g.db.add(mod)

	return redirect(f'/h/{sub.name}')

@app.post("/kick/<pid>")
@is_not_permabanned
def kick(v, pid):
	try: pid = int(pid)
	except: abort(400)

	post = get_post(pid)

	if not post.sub: abort(403)
	if not v.mods(post.sub): abort(403)

	post.sub = None
	g.db.add(post)

	cache.delete_memoized(frontlist)

	return {"message": "Post kicked successfully!"}

@app.post("/rehole/<pid>", defaults={'hole': ''})
@app.post("/rehole/<pid>/<hole>")
@admin_level_required(2)
def rehole_post(v, pid, hole):
	post = get_post(pid)

	sub_from = post.sub
	sub_to = hole.strip().lower()
	sub_to = g.db.query(Sub).filter_by(name=sub_to).one_or_none()
	sub_to = sub_to.name if sub_to else None

	if sub_from == sub_to:
		abort(400)
	post.sub = sub_to
	g.db.add(post)

	sub_from_str = 'frontpage' if sub_from is None else \
		f'<a href="/h/{sub_from}">/h/{sub_from}</a>'
	sub_to_str = 'frontpage' if sub_to is None else \
		f'<a href="/h/{sub_to}">/h/{sub_to}</a>'
	ma = ModAction(
		kind='move_hole',
		user_id=v.id,
		target_submission_id=post.id,
		_note=f'{sub_from_str} → {sub_to_str}',
	)
	g.db.add(ma)

	on_post_hole_entered(post)

	return {"message": f"Post moved to {sub_to_str}!"}

def on_post_hole_entered(post):
	if not post.sub or not post.subr:
		return
	hole = post.subr.name

	# Notify hole followers
	if not post.ghost and not post.private:
		text = f"<a href='/h/{hole}'>/h/{hole}</a> has a new " \
			 + f"post: [{post.title}]({post.shortlink})"
		cid = notif_comment(text, autojanny=True)
		for follow in post.subr.followers:
			user = get_account(follow.user_id)
			if post.club and not user.paid_dues: continue
			add_notif(cid, user.id)

@app.get('/h/<sub>/settings')
@is_not_permabanned
def sub_settings(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)

	if not v.mods(sub.name): abort(403)

	return render_template('sub/settings.html', v=v, sidebar=sub.sidebar, sub=sub)


@app.post('/h/<sub>/sidebar')
@limiter.limit("1/second;30/minute;200/hour;1000/day")
@limiter.limit("1/second;30/minute;200/hour;1000/day", key_func=lambda:f'{request.host}-{session.get("lo_user")}')
@is_not_permabanned
def post_sub_sidebar(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)
	
	if not v.mods(sub.name): abort(403)

	sub.sidebar = request.values.get('sidebar', '').strip()[:500]
	sub.sidebar_html = sanitize(sub.sidebar)
	if len(sub.sidebar_html) > 1000: return "Sidebar is too big!"

	g.db.add(sub)


	return redirect(f'/h/{sub.name}/settings')


@app.post('/h/<sub>/css')
@limiter.limit("1/second;30/minute;200/hour;1000/day")
@limiter.limit("1/second;30/minute;200/hour;1000/day", key_func=lambda:f'{request.host}-{session.get("lo_user")}')
@is_not_permabanned
def post_sub_css(v, sub):
	sub = g.db.query(Sub).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)
	
	if not v.mods(sub.name): abort(403)

	css = request.values.get('css', '').strip()


	for i in css_regex.finditer(css):
		url = i.group(0)
		if not is_safe_url(url):
			domain = tldextract.extract(url).registered_domain
			error = f"The domain '{domain}' is not allowed, please use one of these domains\n\n{approved_embed_hosts}."
			return render_template('sub/settings.html', v=v, sidebar=sub.sidebar, sub=sub, error=error)



	sub.css = css
	g.db.add(sub)

	return redirect(f'/h/{sub.name}/settings')


@app.get("/h/<sub>/css")
def get_sub_css(sub):
	sub = g.db.query(Sub.css).filter_by(name=sub.strip().lower()).one_or_none()
	if not sub: abort(404)
	resp=make_response(sub.css or "")
	resp.headers.add("Content-Type", "text/css")
	return resp


@app.post("/h/<sub>/banner")
@limiter.limit("1/second;10/day")
@limiter.limit("1/second;10/day", key_func=lambda:f'{request.host}-{session.get("lo_user")}')
@is_not_permabanned
def sub_banner(v, sub):
	if request.headers.get("cf-ipcountry") == "T1": return {"error":"Image uploads are not allowed through TOR."}, 403

	sub = g.db.query(Sub).filter_by(name=sub.lower().strip()).one_or_none()
	if not sub: abort(404)

	if not v.mods(sub.name): abort(403)

	file = request.files["banner"]

	name = f'/images/{time.time()}'.replace('.','') + '.webp'
	file.save(name)
	bannerurl = process_image(name)

	if bannerurl:
		if sub.bannerurl and '/images/' in sub.bannerurl:
			fpath = '/images/' + sub.bannerurl.split('/images/')[1]
			if path.isfile(fpath): os.remove(fpath)
		sub.bannerurl = bannerurl
		g.db.add(sub)

	return redirect(f'/h/{sub.name}/settings')

@app.post("/h/<sub>/sidebar_image")
@limiter.limit("1/second;10/day")
@limiter.limit("1/second;10/day", key_func=lambda:f'{request.host}-{session.get("lo_user")}')
@is_not_permabanned
def sub_sidebar(v, sub):
	if request.headers.get("cf-ipcountry") == "T1": return {"error":"Image uploads are not allowed through TOR."}, 403

	sub = g.db.query(Sub).filter_by(name=sub.lower().strip()).one_or_none()
	if not sub: abort(404)

	if not v.mods(sub.name): abort(403)
	
	file = request.files["sidebar"]
	name = f'/images/{time.time()}'.replace('.','') + '.webp'
	file.save(name)
	sidebarurl = process_image(name)

	if sidebarurl:
		if sub.sidebarurl and '/images/' in sub.sidebarurl:
			fpath = '/images/' + sub.sidebarurl.split('/images/')[1]
			if path.isfile(fpath): os.remove(fpath)
		sub.sidebarurl = sidebarurl
		g.db.add(sub)

	return redirect(f'/h/{sub.name}/settings')

@app.get("/holes")
@auth_desired
def subs(v):
	subs = g.db.query(Sub, func.count(Submission.sub)).outerjoin(Submission, Sub.name == Submission.sub).group_by(Sub.name).order_by(func.count(Submission.sub).desc()).all()
	return render_template('sub/subs.html', v=v, subs=subs)

def sub_inactive_purge_task():
	if not HOLE_INACTIVITY_DELETION:
		return False

	one_week_ago = time.time() - 604800
	active_holes = [x[0] for x in g.db.query(Submission.sub).distinct() \
		.filter(Submission.sub != None, Submission.created_utc > one_week_ago).all()]

	dead_holes = g.db.query(Sub).filter(Sub.name.notin_(active_holes)).all()
	names = [x.name for x in dead_holes]

	mods = g.db.query(Mod).filter(Mod.sub.in_(names)).all()
	for x in mods:
		send_repeatable_notification(x.user_id, f":marseyrave: /h/{x.sub} has been deleted for inactivity after one week without new posts. All posts in it have been moved to the main feed :marseyrave:")

	admins = [x[0] for x in g.db.query(User.id).filter(User.admin_level > 1).all()]
	for name in names:
		for admin in admins:
			send_repeatable_notification(admin, f":marseyrave: /h/{name} has been deleted for inactivity after one week without new posts. All posts in it have been moved to the main feed :marseyrave:")

	posts = g.db.query(Submission).filter(Submission.sub.in_(names)).all()
	for post in posts:
		post.sub = None
		g.db.add(post)

	to_delete = mods \
		+ g.db.query(Exile).filter(Exile.sub.in_(names)).all() \
		+ g.db.query(SubBlock).filter(SubBlock.sub.in_(names)).all() \
		+ g.db.query(SubSubscription).filter(SubSubscription.sub.in_(names)).all()

	for x in to_delete:
		g.db.delete(x)
	g.db.flush()

	for x in dead_holes:
		g.db.delete(x)

	return True
