
import frappe
from frappe import _


# ============================================================
# BLOGGER
# ============================================================

@frappe.whitelist(allow_guest=True)
def create_blogger(**kwargs):
    """
    Create a Blogger.

    Required:
        blogger_name

    Optional:
        user
        bio
        avatar
    """

    blogger_name = kwargs.get("blogger_name")

    if not blogger_name:
        frappe.throw(_("Blogger name is required"))

    # Check duplicate
    if frappe.db.exists("Blogger", {"name": blogger_name}):
        frappe.throw(_("Blogger already exists"))

    doc = frappe.new_doc("Blogger")

    # IMPORTANT:
    # The exact field names depend on your Frappe version.
    # Check with:
    # frappe.get_meta("Blogger").fields

    doc.name = blogger_name

    if kwargs.get("user"):
        doc.user = kwargs.get("user")

    if kwargs.get("bio"):
        doc.bio = kwargs.get("bio")
    if kwargs.get("short_name"):
            doc.short_name = kwargs.get("short_name")
    if kwargs.get("full_name"):
        doc.full_name = kwargs.get("full_name")

    if kwargs.get("avatar"):
        doc.avatar = kwargs.get("avatar")

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": 200,
        "message": "Blogger created successfully",
        "data": doc.as_dict()
    }


@frappe.whitelist(allow_guest=True)
def get_bloggers():
    """
    Get all bloggers.
    """

    bloggers = frappe.get_all(
        "Blogger",
        fields=["*"],
        order_by="creation desc"
    )

    return {
        "status": 200,
        "message": "Bloggers fetched successfully",
        "data": bloggers
    }


@frappe.whitelist()
def get_blogger(name=None):
    """
    Get single blogger.
    """

    if not name:
        frappe.throw(_("Blogger name is required"))

    if not frappe.db.exists("Blogger", name):
        frappe.throw(_("Blogger not found"))

    doc = frappe.get_doc("Blogger", name)

    return {
        "status": 200,
        "message": "Blogger fetched successfully",
        "data": doc.as_dict()
    }


@frappe.whitelist(allow_guest=True)
def update_blogger(name=None, **kwargs):
    """
    Update Blogger.
    """

    if not name:
        frappe.throw(_("Blogger name is required"))

    if not frappe.db.exists("Blogger", name):
        frappe.throw(_("Blogger not found"))

    doc = frappe.get_doc("Blogger", name)

    allowed_fields = [
        "user",
        "bio",
        "avatar"
    ]

    for field in allowed_fields:
        if field in kwargs:
            doc.set(field, kwargs.get(field))

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": 200,
        "message": "Blogger updated successfully",
        "data": doc.as_dict()
    }


# ============================================================
# BLOG POST
# ============================================================

@frappe.whitelist(allow_guest=True)
def create_blog_post(**kwargs):
    """
    Create a Blog Post.

    Required:
        title

    Optional:
        blog_intro
        content
        blog_category
        blogger
        published
        route
        meta_title
        meta_description
        meta_image
    """

    title = kwargs.get("title")

    if not title:
        frappe.throw(_("Blog title is required"))

    # --------------------------------------------------------
    # Check duplicate title
    # --------------------------------------------------------

    if frappe.db.exists("Blog Post", {"title": title}):
        frappe.throw(_("Blog post with this title already exists"))

    # --------------------------------------------------------
    # Create document
    # --------------------------------------------------------

    doc = frappe.new_doc("Blog Post")

    doc.title = title

    if kwargs.get("blog_intro"):
        doc.blog_intro = kwargs.get("blog_intro")

    if kwargs.get("content"):
        doc.content = kwargs.get("content")

    if kwargs.get("blog_category"):
        doc.blog_category = kwargs.get("blog_category")

    if kwargs.get("blogger"):
        doc.blogger = kwargs.get("blogger")

    if kwargs.get("published") is not None:
        doc.published = int(kwargs.get("published"))

    if kwargs.get("route"):
        doc.route = kwargs.get("route")

    if kwargs.get("meta_title"):
        doc.meta_title = kwargs.get("meta_title")

    if kwargs.get("meta_description"):
        doc.meta_description = kwargs.get("meta_description")

    if kwargs.get("meta_image"):
        doc.meta_image = kwargs.get("meta_image")

    # --------------------------------------------------------
    # Insert
    # --------------------------------------------------------

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": 200,
        "message": "Blog post created successfully",
        "data": doc.as_dict()
    }


@frappe.whitelist(allow_guest=True)
def get_blog_posts(
    page=1,
    page_size=10,
    published_only=1
):
    """
    Get Blog Posts with pagination.

    Example:
        /api/method/stridenex_app.api.blog.get_blog_posts
    """

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        frappe.throw(_("page and page_size must be numbers"))

    if page < 1:
        page = 1

    if page_size < 1:
        page_size = 10

    if page_size > 100:
        page_size = 100

    limit_start = (page - 1) * page_size

    # --------------------------------------------------------
    # Filters
    # --------------------------------------------------------

    filters = {}

    if int(published_only):
        filters["published"] = 1

    # --------------------------------------------------------
    # Get total
    # --------------------------------------------------------

    total_count = frappe.db.count(
        "Blog Post",
        filters=filters
    )

    # --------------------------------------------------------
    # Get records
    # --------------------------------------------------------

    blogs = frappe.get_all(
        "Blog Post",
        filters=filters,
        fields=[
            "name",
            "title",
            "blog_intro",
            "blog_category",
            "blogger",
            "published",
            "route",
            "creation",
            "modified"
        ],
        order_by="creation desc",
        limit_start=limit_start,
        limit_page_length=page_size
    )

    return {
        "status": 200,
        "message": "Blog posts fetched successfully",
        "data": blogs,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size
        }
    }


@frappe.whitelist(allow_guest=True)
def get_blog_post(name=None):
    """
    Get single Blog Post.
    """

    if not name:
        frappe.throw(_("Blog post name is required"))

    if not frappe.db.exists("Blog Post", name):
        frappe.throw(_("Blog post not found"))

    doc = frappe.get_doc("Blog Post", name)

    return {
        "status": 200,
        "message": "Blog post fetched successfully",
        "data": doc.as_dict()
    }


@frappe.whitelist(allow_guest=True)
def update_blog_post(name=None, **kwargs):
    """
    Update Blog Post.
    """

    if not name:
        frappe.throw(_("Blog post name is required"))

    if not frappe.db.exists("Blog Post", name):
        frappe.throw(_("Blog post not found"))

    doc = frappe.get_doc("Blog Post", name)

    allowed_fields = [
        "title",
        "blog_intro",
        "content",
        "blog_category",
        "blogger",
        "published",
        "route",
        "meta_title",
        "meta_description",
        "meta_image"
    ]

    for field in allowed_fields:
        if field in kwargs:
            doc.set(field, kwargs.get(field))

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": 200,
        "message": "Blog post updated successfully",
        "data": doc.as_dict()
    }


@frappe.whitelist(allow_guest=True)
def delete_blog_post(name=None):
    """
    Delete Blog Post.
    """

    if not name:
        frappe.throw(_("Blog post name is required"))

    if not frappe.db.exists("Blog Post", name):
        frappe.throw(_("Blog post not found"))

    frappe.delete_doc(
        "Blog Post",
        name,
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "status": 200,
        "message": "Blog post deleted successfully"
    }


### API URLs

# After creating the file, your APIs will be:

# ```text
# /api/method/stridenex_app.api.blog.create_blogger

# /api/method/stridenex_app.api.blog.get_bloggers

# /api/method/stridenex_app.api.blog.get_blogger

# /api/method/stridenex_app.api.blog.update_blogger


# /api/method/stridenex_app.api.blog.create_blog_post

# /api/method/stridenex_app.api.blog.get_blog_posts

# /api/method/stridenex_app.api.blog.get_blog_post

# /api/method/stridenex_app.api.blog.update_blog_post

# /api/method/stridenex_app.api.blog.delete_blog_post
# ```

# ### Create Blogger

# ```json
# {
#     "blogger_name": "John Doe",
#     "user": "john@example.com",
#     "bio": "Technology writer"
# }
# ```

# ### Create Blog Post

# ```json
# {
#     "title": "How AI Is Changing Education",
#     "blog_intro": "Artificial intelligence is transforming education.",
#     "content": "<h2>Introduction</h2><p>AI is changing how students learn...</p>",
#     "blog_category": "Technology",
#     "blogger": "John Doe",
#     "published": 1
# }
# ```

# ### Get published blogs

# ```text
# GET /api/method/stridenex_app.api.blog.get_blog_posts?page=1&page_size=10&published_only=1
# ```

# ### Get all blogs including drafts

# ```text
# GET /api/method/stridenex_app.api.blog.get_blog_posts?page=1&page_size=10&published_only=0
# ```

# **One important point:** the exact fields in Frappe's built-in `Blogger` and `Blog Post` can differ by Frappe version. Before using the code, check them from your bench:

# ```bash
# cd ~/frappe-bench

# bench --site devstridenex.quantcloud.in console
# ```

# Then:

# ```python
# frappe.get_meta("Blog Post").fields
# frappe.get_meta("Blogger").fields
# ```

# If you paste those two outputs here, I can adjust the Python code to **exactly match your Frappe v16 DocTypes**, including category, author, image, SEO, comments, route, and publishing fields.
