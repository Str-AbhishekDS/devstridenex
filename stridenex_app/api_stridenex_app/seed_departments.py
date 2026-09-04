import frappe


def seed_departments():
    DEPARTMENTS = [
        # Group 1
        "Automobile Engineering",
        "Chemical Engineering",
        "Civil Engineering",
        "Computer Engineering",
        "Electronics and Telecommunication Engineering",
        "Artificial Intelligence and Machine Learning",
        "Mechanical Engineering",
        "General Engineering",
        # Group 2
        "CSE(Artificial Intelligence and Data Science)",
        "Electrical and Computer Engineering",
        "Electronics and Computer Science",
        "Instrumentation and control engineering",
        # Group 3
        "Heat Power Engineering",
        "Structural Engineering",
        "Electrical Engineering",
        "Design Engineering",
        # Group 4
        "Arificial Intelligence and Mechine Learning",
        "Electronics & Computer Engineering",
        "Basic Science and Humanities",
        # Group 5
        "Civil",
        "Computer",
        "Electrical",
        "E & Tc",
        "Mechanical",
        "Computer Science",
        "Engineering(AI/ML)",
        "Electronics and Computer",
        "Science",
        "General Science",
        # Group 6
        "MBA",
        # Group 7
        "Information Technology",
        "Electronics & Telecommunication",
        "Computer Science and Engineeing",
        "Ariticial Intelligence and Data Science",
        "Civil Construction and Management",
        "Master of Computer Application (MCA)",
        # Group 8
        "Computer Science & Engineering",
        "Computer Science & Engg. (Data Science)",
        # Group 9
        "Computer Science and Engineering (AIML)",
        "Mechanical and Mechatronics Engineering (Additive Manufacturing)",
        "Electrical, Electronics and Power Engineering",
        # Group 10
        "Artificial Intelligence & Mechine Learning",
        "Electronics and computer Engineering",
        # Group 11
        "Advanced Diploma in Cyber Security management",
        # Group 12
        "Artificial Intelligence and Data Science",
        "Electronics and Telecommunications Engineering",
        "Electronics and Computer Engineering",
        # Group 13
        "Master of Business Administration",
        # Group 14
        "Mechanical Engineering (Design)",
        "Mechanical Engineering (Production)",
        "Civil Engineering (Construction Management)",
        # Group 15
        "Agronomy",
        "Horticulture",
        "Agril Economics",
        "Agricultural Entomology",
        "Extension Education",
        "Genetics and Plant Breedding",
        "Plant Pathology",
        "Animal Husbandry and Dairy Science",
        "Agricultural Botany",
        "Agri Engineering",
        # Group 16
        "Mechatronics Engineering",
        "Artificial Intelligence and Machine Learning (AI & ML)",
        # Group 17
        "Computer Science and Engineering (Artificial Intelligence and Machine Learning)",
        "Computer Science and Information Technology",
        "Electronics & Tele-communication Engineering",
        "Robotics and Automation",
        # Group 18 (previous run - will be skipped if exist)
        "Construction Management",
        "Electronics Engineering",
        "Mechanical Engineering (Thermal Engineering)",
        "Power Systems and Power Electronics",
        "Mechanical Engineering Design",
        # Group 19
        "Bachelor of Computer Application",
        "Master of computer application",
        # Group 20
        "Bachelor of Business Administration",
        "MBA (Innovation Entrepreneurship And Venture Development)",
        # Group 21
        "Aeronautical Engineering",
        "Food Technology",
        "Artificial Intelligence (AI) and Data Science",
        "Computer Science & Engineering (Internet of Things and Cyber Security Including Block Chain Technology)",
        "Robotics And Artificial Intelligence",
        # Group 22
        "Bachelor of Business Administration (BBA)",
        "Bachelor of Computer Application (BCA)",
        # Group 23
        "Electrical Power System",
        "Civil Engineering (Computer Aided Structural Engineering)",
        "Computer Science And Engineering",
    ]

    # Deduplicate while preserving order
    seen = set()
    unique_departments = []
    for d in DEPARTMENTS:
        if d not in seen:
            seen.add(d)
            unique_departments.append(d)

    created = []
    skipped = []

    for dept_name in unique_departments:
        existing = frappe.db.get_value(
            "College Department", {"department_name": dept_name}, "name"
        )
        if existing:
            skipped.append(dept_name)
        else:
            dept_doc = frappe.get_doc(
                {
                    "doctype": "College Department",
                    "department_name": dept_name,
                }
            )
            dept_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            created.append(dept_name)

    print(f"\n{'='*60}")
    print(f"  CREATED ({len(created)}):")
    for d in created:
        print(f"  [+] {d}")
    print(f"\n  SKIPPED - already exists ({len(skipped)}):")
    for d in skipped:
        print(f"  [-] {d}")
    print(
        f"\n  TOTAL: {len(unique_departments)} processed | {len(created)} created | {len(skipped)} skipped"
    )
    print(f"{'='*60}")
