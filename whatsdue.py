@app.route('/whatsdue', methods=['GET', 'POST'])
def whatsdue() -> Response:
    if request.method == 'GET':
        return render_template("whatsdue.html")
    else:
        subjects = [request.form[f"subject{i}"] for i in range(1, 6)]
        data = get_whats_due(set(subjects))
        return jsonify(data)

@app.route('/whats-due', methods=['GET'])
@login_required
def whats_due() -> Response:
    """
    Grabs the upcoming assessment infomation for the current user.
    """
    return ok(current_user.whats_due)

def get_whats_due(subjects: Set[str]) -> List[Dict[str, str]]:
    """
    Takes a list of course codes, finds their course profile id numbers, parses
    UQ's PHP gateway, then returns the coming assessment.
    """
    course_url = 'https://www.uq.edu.au/study/course.html?course_code='
    assessment_url = 'https://www.courses.uq.edu.au/student_section_report' +\
        '.php?report=assessment&profileIds='

    courses_id = []
    for course in subjects:
        try:
            response = urllib.request.urlopen(course_url + course.upper())
            html = response.read().decode('utf-8')
        except:
            continue  # Ignore in the case of failure
        try:
            profile_id_regex = re.compile('profileId=\d*')
            profile_id = profile_id_regex.search(html).group()
            if profile_id != None:
                # Slice to strip the 'profileID='
                courses_id.append(profile_id[10:])
        except:
            continue  # Ignore in the case of failure

    courses = ",".join(courses_id)
    response = urllib.request.urlopen(assessment_url + courses)
    html = response.read().decode('utf-8')
    html = re.sub('<br />', ' ', html)

    soup = BeautifulSoup(html, "html5lib")
    table = soup.find('table', attrs={'class': 'tblborder'})
    rows = table.find_all('tr')[1:]  # ignore the top row of the table

    data = []
    for row in rows:
        cols = [ ele.text.strip() for ele in row.find_all('td') ]

        subject = cols[0].split(" ")[0] # Strip out irrelevant BS about the subject
        date = cols[2]

        # Some dates are ranges. We only care about the end
        if " - " in date:
            _, date = date.split(" - ")

        now = datetime.now(BRISBANE_TIME_ZONE)

        def try_parsing_date(xs: str) -> Optional[datetime]:
            """
            Brute force all the date formats I've seen UQ use.
            """
            # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
            for fmt in ("%d %b %Y: %H:%M", "%d %b %Y : %H:%M", "%d %b %y %H:%M"):
                try:
                    return datetime.strptime(xs, fmt).replace(tzinfo=BRISBANE_TIME_ZONE)
                except ValueError:
                    pass

            return None

        due = try_parsing_date(date)

        if due and due < now:
            logging.debug(f"Culling assessment due on {due}")
            continue # Don't add if it's passed deadline

        # Otherwise, add it regardless
        data.append({"subject": subject, "description": cols[1],
                     "date": cols[2], "weighting": cols[3]})

    return data