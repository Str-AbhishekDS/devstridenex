import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days

class MentorPayoutSheet(Document):
	def validate(self):
		# 1. Set Title
		self.title = f"Payout Sheet: {self.start_date} to {self.end_date} ({self.payout_cycle})"
		
		# 2. Preserve user selections (released checkbox)
		released_map = {}
		for row in self.get("mentors") or []:
			if row.mentor and row.released:
				released_map[row.mentor] = True
		for row in self.get("summary") or []:
			if row.mentor and row.released:
				released_map[row.mentor] = True

		# 3. Fetch default settings
		settings = frappe.get_single("Mentor Payout Settings")
		
		# Retrieve TDS settings
		tds_threshold = float(getattr(settings, "tds_threshold", 50000.0) or 50000.0)
		tds_rate = float(getattr(settings, "tds_rate", 10.0) or 10.0)

		# Retrieve commission tiers
		tiers = []
		for tier in settings.get("commission_tiers") or []:
			tiers.append({
				"threshold": float(tier.threshold or 0),
				"rate": float(tier.commission_rate or 0) / 100.0
			})
		if not tiers:
			tiers = [        
				{"threshold": 0.0, "rate": 0.15},
				{"threshold": 50000.0, "rate": 0.12},
				{"threshold": 100000.0, "rate": 0.10}
			]
		tiers = sorted(tiers, key=lambda x: x["threshold"])

		# Retrieve penalty rates 
		penalty_rates = {                 
			"1:1 Mentorship": float(getattr(settings, "one_on_one_penalty", 15.0) or 15.0),
			"Group Session": float(getattr(settings, "group_session_penalty", 15.0) or 15.0),
			"Async Review": float(getattr(settings, "async_review_penalty", 15.0) or 15.0),
			"Workshop": float(getattr(settings, "workshop_penalty", 15.0) or 15.0)
		}

		# 4. Query eligible bookings in date range (Completed or Missed/Absent, and currently Unpaid)
		bookings = frappe.get_all(
			"Mentor Session Booking",
			filters={
				"session_date": ["between", [self.start_date, self.end_date]],
				"payout_status": "Unpaid"
			},
			fields=["name", "mentor", "student", "session_date", "offering_type", "amount_paid", "status", "mentor_absent"]
		)

		# 5. Populate intermediate lists & calculate
		sessions_rows = []
		penalties_rows = []
		
		# Mentor calculations map
		mentor_data = {}

		for b in bookings:
			mentor = b.mentor
			if not mentor:
				continue

			if mentor not in mentor_data:
				mentor_data[mentor] = {
					"sessions_count": 0,
					"gross_amount": 0.0,
					"refund_amount": 0.0,
					"penalty_amount": 0.0,
					"commission_rate": 15.0,
					"commission_amount": 0.0,
					"earned_amount": 0.0,
					"tds_amount": 0.0,
					"net_payout": 0.0
				}

			amount = float(b.amount_paid or 0)

			# Case A: Missed/Absent session -> Penalty & Refund apply
			if b.mentor_absent:
				# Find penalty rate based on type
				rate = penalty_rates.get(b.offering_type, 15.0)
				penalty_val = (rate / 100.0) * amount
				
				penalties_rows.append({
					"mentor": mentor,
					"booking": b.name,
					"offering_type": b.offering_type,
					"session_fee": amount,
					"penalty_rate": rate,
					"penalty_amount": penalty_val
				})
				
				mentor_data[mentor]["refund_amount"] += amount
				mentor_data[mentor]["penalty_amount"] += penalty_val

			# Case B: Completed session -> Earns Gross
			elif b.status == "Completed":
				sessions_rows.append({
					"booking": b.name,
					"mentor": mentor,
					"student": b.student,
					"session_date": b.session_date,
					"offering_type": b.offering_type,
					"amount_paid": amount,
					"status": b.status
				})
				
				mentor_data[mentor]["gross_amount"] += amount
				mentor_data[mentor]["sessions_count"] += 1

		# Group and calculate commission & net payouts for each mentor
		mentors_rows = []
		summary_rows = []

		for mentor, data in mentor_data.items():
			# Apply tiered commission rate based on Gross
			comm_rate = 15.0 # fallback default
			for tier in tiers:
				if data["gross_amount"] >= tier["threshold"]:
					comm_rate = tier["rate"] * 100.0
			
			data["commission_rate"] = comm_rate
			data["commission_amount"] = (comm_rate / 100.0) * data["gross_amount"]
			
			# Earned amount is Gross - Commission - Refund - Penalty
			data["earned_amount"] = data["gross_amount"] - data["commission_amount"] - data["refund_amount"] - data["penalty_amount"]
			
			# Calculate TDS if earned earnings >= threshold
			tds_amount = 0.0
			actual_tds_rate = 0.0
			if data["earned_amount"] >= tds_threshold:
				tds_amount = (tds_rate / 100.0) * data["earned_amount"]
				actual_tds_rate = tds_rate

			data["tds_amount"] = tds_amount
			data["tds_rate"] = actual_tds_rate
			# Net = Earned - TDS
			data["net_payout"] = data["earned_amount"] - tds_amount
			
			# Check if released was previously selected by the user
			is_released = released_map.get(mentor, False)

			row_dict = {
				"released": 1 if is_released else 0,
				"mentor": mentor,
				"total_sessions": data["sessions_count"],
				"gross_amount": data["gross_amount"],
				"commission_rate": data["commission_rate"],
				"commission_amount": data["commission_amount"],
				"earned_amount": data["earned_amount"],
				"refund_amount": data["refund_amount"],
				"penalty_amount": data["penalty_amount"],    
				"tds_rate": data["tds_rate"],
				"tds_amount": data["tds_amount"],
				"net_payout": data["net_payout"],
				"status": "Draft"
			}
			mentors_rows.append(row_dict)

			summary_dict = {
				"released": 1 if is_released else 0,
				"mentor": mentor,
				"gross_amount": data["gross_amount"],
				"commission_amount": data["commission_amount"],
				"earned_amount": data["earned_amount"],
				"refund_amount": data["refund_amount"],
				"total_penalties": data["penalty_amount"],
				"tds_rate": data["tds_rate"],
				"tds_amount": data["tds_amount"],
				"net_payout": data["net_payout"],
				"status": "Draft"
			}
			summary_rows.append(summary_dict)

		# 6. Set child tables
		self.set("mentors", [])
		self.set("sessions", [])
		self.set("penalties", [])
		self.set("summary", [])

		for row in mentors_rows:
			self.append("mentors", row)
		for row in sessions_rows:
			self.append("sessions", row)
		for row in penalties_rows:
			self.append("penalties", row)
		for row in summary_rows:
			self.append("summary", row)

	def on_submit(self):
		# Create dynamic supplier creation/linking and generate Purchase Invoices for released mentors
		company = frappe.defaults.get_global_default("company") or "Stridenex"
		
		credit_to = frappe.db.get_value("Account", {"account_type": "Payable", "company": company}, "name")
		if not credit_to:
			credit_to = frappe.db.get_value("Account", {"company": company, "is_group": 0, "root_type": "Liability"}, "name")

		# Load accounts setting doc
		accounts_setting = None
		try:
			accounts_setting = frappe.get_single("Mentor Payout Accounts Setting")
		except Exception:
			pass

		# Get or create the Mentor Services item
		configured_item = (accounts_setting.mentor_services_item if accounts_setting and accounts_setting.mentor_services_item else None) or "Mentor Services"
		mentor_services_item = get_or_create_item(configured_item)

		# Get or create specific accounts
		mentor_expense_account = (accounts_setting.mentor_expense_account if accounts_setting and accounts_setting.mentor_expense_account else None) or get_account_by_name_or_create("Mentor Expense", "Expense Account", ["Direct Expenses", "Expenses"], company)
		commission_account = (accounts_setting.mentor_commission_account if accounts_setting and accounts_setting.mentor_commission_account else None) or get_account_by_name_or_create("Mentor Commission", "Income Account", ["Indirect Income", "Direct Income", "Income"], company)
		penalty_account = (accounts_setting.penalty_payable_account if accounts_setting and accounts_setting.penalty_payable_account else None) or get_account_by_name_or_create("Penalty Payable", "Liability", ["Current Liabilities"], company)
		tds_account = (accounts_setting.tds_payable_account if accounts_setting and accounts_setting.tds_payable_account else None) or get_account_by_name_or_create("TDS Payable", "Tax", ["Duties and Taxes", "Current Liabilities"], company)

		released_mentors = set()
		for row in self.mentors:
			if row.released:
				released_mentors.add(row.mentor)
				row.status = "Approved"

		for row in self.summary:
			if row.mentor in released_mentors:
				row.status = "Approved"
				row.released = 1

		# Update Booking Statuses for released mentors
		bookings = frappe.get_all(
			"Mentor Session Booking",
			filters={
				"session_date": ["between", [self.start_date, self.end_date]],
				"payout_status": "Unpaid",
				"mentor": ["in", list(released_mentors)]
			},
			fields=["name", "mentor"]
		)

		for b in bookings:
			frappe.db.set_value("Mentor Session Booking", b.name, {
				"payout_status": "Processing",
				"payout_reference": self.name
			})

		# Generate Purchase Invoices for released payouts
		for row in self.summary:
			if not row.released or row.net_payout <= 0:
				continue
			
			supplier = get_or_create_supplier(row.mentor)
			
			items = []
			
			# 1. Gross completed sessions mentorship (Debit)
			items.append({
				"item_code": mentor_services_item,
				"item_name": f"Mentorship Gross completed - Sheet: {self.name}",
				"qty": 1,
				"rate": row.gross_amount,
				"price_list_rate": row.gross_amount,
				"amount": row.gross_amount,
				"expense_account": mentor_expense_account
			})
			
			# 2. Commission Deduction (Credit)
			if row.commission_amount > 0:
				items.append({
					"item_code": mentor_services_item,
					"item_name": f"Commission Deduction - Sheet: {self.name}",
					"qty": 1,
					"rate": -row.commission_amount,
					"price_list_rate": -row.commission_amount,
					"amount": -row.commission_amount,
					"expense_account": commission_account
				})
				
			# 3. Student Refund Deduction (Credit)
			if row.refund_amount > 0:
				items.append({
					"item_code": mentor_services_item,
					"item_name": f"Student Refund Deduction - Sheet: {self.name}",
					"qty": 1,
					"rate": -row.refund_amount,
					"price_list_rate": -row.refund_amount,
					"amount": -row.refund_amount,
					"expense_account": penalty_account
				})
				
			# 4. Absenteeism Penalty Deduction (Credit)
			if row.total_penalties > 0:
				items.append({                                   
					"item_code": mentor_services_item,
					"item_name": f"Absenteeism Penalty Deduction - Sheet: {self.name}",
					"qty": 1,
					"rate": -row.total_penalties,                                
					"price_list_rate": -row.total_penalties,
					"amount": -row.total_penalties,
					"expense_account": penalty_account
				})
				 
			pi = frappe.get_doc({                            
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"company": company,
				"posting_date": frappe.utils.today(),         
				"credit_to": credit_to,
				"ignore_pricing_rule": 1,
				"apply_tds": 1,             
				"items": items             
			})
			pi.insert(ignore_permissions=True)                 
			pi.submit()              
			
			frappe.msgprint(f"Generated Purchase Invoice {pi.name} for mentor {row.mentor}")     

def get_or_create_supplier(mentor_email):
	supplier_name = frappe.db.get_value("Supplier", {"email_id": mentor_email}, "name")
	if not supplier_name:
		supplier_name = frappe.db.get_value("Supplier", {"supplier_name": mentor_email}, "name")
	
	twc = "Professional Fees - Individual" if frappe.db.exists("Tax Withholding Category", "Professional Fees - Individual") else None

	if not supplier_name:
		s_dict = {
			"doctype": "Supplier",
			"supplier_name": mentor_email,
			"supplier_group": "All Supplier Groups",
			"email_id": mentor_email
		}
		if twc:
			s_dict["tax_withholding_category"] = twc
		s = frappe.get_doc(s_dict)
		s.insert(ignore_permissions=True)
		supplier_name = s.name
	else:
		if twc:
			frappe.db.set_value("Supplier", supplier_name, "tax_withholding_category", twc)
			frappe.db.commit()
	return supplier_name

def get_account_by_name_or_create(account_name, account_type, parent_candidates, company):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	full_account_name = f"{account_name} - {abbr}"
	
	# Check if full name exists
	account = frappe.db.get_value("Account", {"name": full_account_name}, "name")
	if not account:
		# Check if standard name exists
		account = frappe.db.get_value("Account", {"account_name": account_name, "company": company}, "name")
	
	if not account:
		# Find a parent account that actually exists
		parent_account = None
		for candidate in parent_candidates:
			p_name = f"{candidate} - {abbr}"
			if frappe.db.exists("Account", p_name):
				parent_account = p_name
				break
			if frappe.db.exists("Account", candidate):
				parent_account = candidate
				break
		
		# Fallbacks if parent candidates not found
		if not parent_account:
			if account_type == "Expense Account":
				parent_account = frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Expense"}, "name")
			elif account_type == "Income Account":
				parent_account = frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Income"}, "name")
			else:
				parent_account = frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Liability"}, "name")
		
		# Create the account
		acc = frappe.get_doc({
			"doctype": "Account",
			"account_name": account_name,
			"account_type": account_type,
			"parent_account": parent_account,
			"company": company, 
			"is_group": 0
		})
		acc.insert(ignore_permissions=True)
		account = acc.name
	return account

def get_or_create_item(item_code="Mentor Services"):
	if not frappe.db.exists("Item", item_code):
		item_group = "Services" if frappe.db.exists("Item Group", "Services") else "All Item Groups"
		uom = "Nos" if frappe.db.exists("UOM", "Nos") else "Unit"
		
		hsn_code = frappe.db.get_value("GST HSN Code", {"hsn_code": ["like", "99%"]}, "name")
		if not hsn_code:
			hsn_code = frappe.db.get_value("GST HSN Code", {}, "name")

		item_dict = {
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code,
			"item_group": item_group,
			"stock_uom": uom,
			"is_stock_item": 0
		}
		if hsn_code:
			item_dict["gst_hsn_code"] = hsn_code

		item = frappe.get_doc(item_dict)
		if frappe.db.exists("Item Tax Template", "GST 18% - QTPL"):
			item.append("taxes", {"item_tax_template": "GST 18% - QTPL"})
		item.insert(ignore_permissions=True)
	else:
		item = frappe.get_doc("Item", item_code)
		if not item.taxes and frappe.db.exists("Item Tax Template", "GST 18% - QTPL"):
			item.append("taxes", {"item_tax_template": "GST 18% - QTPL"})
			item.save(ignore_permissions=True)
	return item_code

def get_or_create_student_customer(student_email):
	customer = frappe.db.get_value("Customer", {"email_id": student_email}, "name")
	if not customer:
		if frappe.db.exists("Customer", student_email):
			customer = student_email
		else:
			full_name = frappe.db.get_value("User", student_email, "full_name") or student_email
			cust_doc = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": full_name,
				"customer_type": "Individual",
				"email_id": student_email,
				"customer_group": "All Customer Groups",
				"territory": "All Territories"
			})
			cust_doc.insert(ignore_permissions=True)
			customer = cust_doc.name
	return customer

def create_paid_sales_invoice_for_booking(booking_doc, payment_ref):
	original_user = frappe.session.user
	try:
		if original_user != "Administrator":
			frappe.set_user("Administrator")

		company = frappe.defaults.get_global_default("company") or "Quantbit Technologies Pvt Ltd"
		student_email = booking_doc.student
		amount = float(booking_doc.amount_paid or 0)
		
		# Resolve setting-based accounts
		accounts_setting = None
		try:
			accounts_setting = frappe.get_single("Mentor Payout Accounts Setting")
		except Exception:
			pass

		sales_account = (accounts_setting.sales_account if accounts_setting and accounts_setting.sales_account else None) or "Sales - QTPL"
		clearing_account = (accounts_setting.razorpay_clearing_account if accounts_setting and accounts_setting.razorpay_clearing_account else None) or "Razorpay Clearing - QTPL"

		# Resolve Customer
		customer = get_or_create_student_customer(student_email)

		# Resolve Item (1:1 Session, Workshop, Group Session, etc.) based on offering_type
		offering_type = booking_doc.offering_type or "1:1 Session"
		item_code = get_or_create_item(offering_type)

		# Create and Submit Sales Invoice
		debit_to = frappe.db.get_value("Account", {"account_type": "Receivable", "company": company}, "name") or f"Debtors - {frappe.db.get_value('Company', company, 'abbr')}"
		invoice = frappe.get_doc({
			"doctype": "Sales Invoice",
			"company": company,
			"customer": customer,
			"posting_date": frappe.utils.today(),
			"due_date": frappe.utils.today(),
			"currency": "INR",
			"debit_to": debit_to,
			"taxes_and_charges": "Output GST In-state - QTPL",
			"items": [{
				"item_code": item_code,
				"qty": 1,
				"rate": amount,
				"income_account": sales_account
			}]
		})
		invoice.set_missing_values()
		invoice.calculate_taxes_and_totals()
		invoice.insert(ignore_permissions=True)
		invoice.submit()

		# Create and Submit Payment Entry to mark Sales Invoice as Paid
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		pe = get_payment_entry("Sales Invoice", invoice.name)
		pe.reference_no = payment_ref
		pe.reference_date = frappe.utils.today()
		pe.paid_to = clearing_account
		pe.insert(ignore_permissions=True)
		pe.submit()

		# Link the Sales Invoice name back to the booking's sales_invoice field if it exists
		if booking_doc.meta.has_field("sales_invoice"):
			booking_doc.db_set("sales_invoice", invoice.name)
		
		# Also link to Subscription History if possible
		sh_name = frappe.db.get_value("Subscription History", {"razorpay_payment_id": payment_ref}, "name")
		if sh_name:
			frappe.db.set_value("Subscription History", sh_name, {
				"sales_invoice_no": invoice.name,
				"payment_entry_no": pe.name
			}, update_modified=False)

		return invoice.name
	except Exception as e:
		frappe.log_error(title="Failed to generate paid Sales Invoice for session booking", message=frappe.get_traceback())
		raise e
	finally:
		if original_user != "Administrator":
			frappe.set_user(original_user)

