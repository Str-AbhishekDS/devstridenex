frappe.ui.form.on("Campus Drive Application", {
    refresh: function (frm) {
        frm.set_df_property("college", "read_only", 1);
    },

    drive: function (frm) {
        if (frm.doc.drive) {
            frappe.db.get_value(
                "Campus Drives",
                frm.doc.drive,
                "college",
                function (value) {
                    if (value && value.college) {
                        frm.set_value("college", value.college);
                    }
                }
            );
        } else {
            frm.set_value("college", "");
        }
    }
});