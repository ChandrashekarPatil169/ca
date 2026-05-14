def post_init_hook(env):
    env['it.user.access.form'].sudo()._setup_user_access_approval_flow()
