
import frappe
from frappe import _





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
        fields=["*"],
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

