app_name = "stridenex_app"
app_title = "Stridenex App"
app_publisher = "QTPL"
app_description = "Educational app"
app_email = "contact@erpdata.io"
app_license = "mit"

# Apps
# ------------------
on_session_creation = [
    "stridenex_app.api_stridenex_app.notification.update_last_activity"
]
# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "stridenex_app",
# 		"logo": "/assets/stridenex_app/logo.png",
# 		"title": "Stridenex App",
# 		"route": "/stridenex_app",
# 		"has_permission": "stridenex_app.api.permission.has_app_permission"
# 	}
# ]
# permission_query_conditions = {
#     "LMS Batch": "stridenex_app.permissions.lms_batch_query"
# }

# has_permission = {
#     "LMS Batch": "stridenex_app.permissions.has_permission"
# }


# permission_query_conditions = {
#     "LMS Batch": "stridenex_app.permissions.lms_batch_query_conditions",
# }

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/stridenex_app/css/stridenex_app.css"
# app_include_js = "/assets/stridenex_app/js/stridenex_app.js"

# include js, css files in header of web template
# web_include_css = "/assets/stridenex_app/css/stridenex_app.css"
# web_include_js = "/assets/stridenex_app/js/stridenex_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "stridenex_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "stridenex_app/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "stridenex_app.utils.jinja_methods",
# 	"filters": "stridenex_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "stridenex_app.install.before_install"
# after_install = "stridenex_app.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "stridenex_app.uninstall.before_uninstall"
# after_uninstall = "stridenex_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "stridenex_app.utils.before_app_install"
# after_app_install = "stridenex_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "stridenex_app.utils.before_app_uninstall"
# after_app_uninstall = "stridenex_app.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "stridenex_app.notifications.get_notification_config"
# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }


doc_events = {
    "Student": {
        "before_save": "stridenex_app.employability.update_score_from_student",
    },
    "Student Skill": {
        "after_insert": "stridenex_app.employability.update_score_from_skill",
        "on_update": "stridenex_app.employability.update_score_from_skill",
        "on_trash": "stridenex_app.employability.update_score_from_skill",
    },
    "Internship Application": {
        "after_insert": "stridenex_app.employability.update_score_from_internship",
        "on_update": "stridenex_app.employability.update_score_from_internship",
        "on_trash": "stridenex_app.employability.update_score_from_internship",
    },
    "Student Project Enrollment": {
        "after_insert": "stridenex_app.employability.update_score_from_project",
        "on_update": "stridenex_app.employability.update_score_from_project",
        "on_trash": "stridenex_app.employability.update_score_from_project",
    },
    "Student Path Enrollment": {
        "after_insert": "stridenex_app.employability.update_score_from_enrollment",
        "on_update": "stridenex_app.employability.update_score_from_enrollment",
        "on_trash": "stridenex_app.employability.update_score_from_enrollment",
    },
    "Student Applications": {
        "on_update": "stridenex_app.api_stridenex_app.notification.project_status_change",
    },
    "Industry Project": {
        "on_submit": "stridenex_app.api_stridenex_app.notification.notify_students_on_new_opportunity"
    },
    "Internship": {
        "on_submit": "stridenex_app.api_stridenex_app.notification.notify_students_on_new_opportunity"
    },
    "Industry Job Profile": {
        "on_submit": "stridenex_app.api_stridenex_app.notification.notify_students_on_new_opportunity"
    },
    # "Internship Application": {
    #     "on_update": "stridenex_app.api_stridenex_app.notification.internship_status_change"
    # },
    # "User": {
    #     "on_update": "stridenex_app.api_stridenex_app.notification.send_onboarding_email"
    # },
    "User": {
           "on_update": [
               "stridenex_app.api_stridenex_app.notification.send_onboarding_email",
               "stridenex_app.api_stridenex_app.notification.send_mentor_onboarding_email",
               "stridenex_app.api_stridenex_app.notification.send_college_onboarding_email",
               "stridenex_app.api_stridenex_app.notification.send_industry_onboarding_email",
               
           ]
       }

}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"stridenex_app.tasks.all"
# 	],
# 	"daily": [
# 		"stridenex_app.tasks.daily"
# 	],
# 	"hourly": [
# 		"stridenex_app.tasks.hourly"
# 	],
# 	"weekly": [
# 		"stridenex_app.tasks.weekly"
# 	],
# 	"monthly": [
# 		"stridenex_app.tasks.monthly"
# 	],
# }

scheduler_events = {
    "cron": {
        "* * * * *": [   # Every 10 minutes
            "stridenex_app.api_stridenex_app.app_utils.delete_expired_otps"
        ],
        # "0 2 * * *": [
        # "stridenex_app.api_stridenex_app.app_utils.send_onboarding_reminders"
        # ],
        # "0 8 * * *": [
        #     "stridenex_app.api_stridenex_app.notification.send_daily_application_summaries"
        # ],
        
    },
    "monthly": [
        "stridenex_app.api_stridenex_app.notification.send_monthly_summary"
    ],
    "monthly": [
          "stridenex_app.api_stridenex_app.notification.send_industry_monthly_summary"
      ]
}

# Testing
# -------

# before_tests = "stridenex_app.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "stridenex_app.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "stridenex_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "stridenex_app.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["stridenex_app.utils.before_request"]
# after_request = ["stridenex_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["stridenex_app.utils.before_job"]
# after_job = ["stridenex_app.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"stridenex_app.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


fixtures = [

    {
        "doctype": "Insights Workbook",
        "filters": [
            ["title", "=", "StrideNex Dashbord"]
        ]
    }

]