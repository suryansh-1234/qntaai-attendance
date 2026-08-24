function getToday() {

    const now = new Date();

    const year = now.getFullYear();

    const month = String(
        now.getMonth() + 1
    ).padStart(2, "0");

    const day = String(
        now.getDate()
    ).padStart(2, "0");

    return `${year}-${month}-${day}`;
}


function formatDate(dateString) {

    const date = new Date(
        dateString + "T00:00:00"
    );

    return date.toLocaleDateString(
        undefined,
        {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric"
        }
    );
}


function escapeHTML(value) {

    const div =
        document.createElement("div");

    div.textContent = value;

    return div.innerHTML;
}


function showMessage(text, type) {

    const message =
        document.getElementById(
            "attendance-message"
        );

    message.textContent = text;

    message.className =
        `message ${type}`;
}


// ------------------------------------------------
// LOAD CURRENT USER
// ------------------------------------------------

async function loadCurrentUser() {

    const response =
        await fetch("/api/me");


    const data =
        await response.json();


    const loginPanel =
        document.getElementById(
            "login-panel"
        );

    const dashboard =
        document.getElementById(
            "dashboard"
        );


    if (!data.authenticated) {

        loginPanel.style.display =
            "block";

        dashboard.style.display =
            "none";

        return;

    }


    loginPanel.style.display =
        "none";

    dashboard.style.display =
        "block";


    document.getElementById(
        "user-name"
    ).textContent = data.name;


    document.getElementById(
        "user-role"
    ).textContent = data.role;


    loadTeam();
}


// ------------------------------------------------
// LOGIN
// ------------------------------------------------

async function login(event) {

    event.preventDefault();


    const input =
        document.getElementById(
            "login-passkey"
        );


    const button =
        document.querySelector(
            "#login-form button"
        );


    const message =
        document.getElementById(
            "login-message"
        );


    const passkey =
        input.value.trim();


    if (!passkey) {

        message.textContent =
            "Enter your passkey.";

        message.className =
            "message error";

        return;

    }


    button.disabled = true;

    button.textContent =
        "Signing in...";


    message.textContent = "";


    try {

        const response =
            await fetch(
                "/api/login",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        passkey: passkey
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            message.textContent =
                data.error ||
                "Sign in failed.";

            message.className =
                "message error";

            return;

        }


        input.value = "";


        await loadCurrentUser();

    }


    catch (error) {

        console.error(error);

        message.textContent =
            "Unable to connect to the server.";

        message.className =
            "message error";

    }


    finally {

        button.disabled = false;

        button.textContent =
            "Sign in";

    }
}


// ------------------------------------------------
// LOAD TEAM
// ------------------------------------------------

async function loadTeam() {

    const container =
        document.getElementById("team");


    const selectedDate =
        document.getElementById(
            "attendance-date"
        ).value;


    try {

        const response =
            await fetch(
                `/api/team?date=${selectedDate}`
            );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );

        }


        const team =
            await response.json();


        let present = 0;

        let late = 0;

        let absent = 0;


        container.innerHTML = "";


        team.forEach(member => {

            if (member.status === "present") {

                present++;

            }

            else if (member.status === "late") {

                late++;

            }

            else {

                absent++;

            }


            const card =
                document.createElement(
                    "div"
                );


            card.className =
                "member-card";


            card.innerHTML = `

                <div class="member-info">

                    <h3>
                        ${escapeHTML(member.name)}
                    </h3>

                    <p>
                        ${escapeHTML(member.role)}
                    </p>

                </div>


                <div class="member-attendance">

                    <span
                        class="status ${member.status}"
                    >
                        ${member.status.toUpperCase()}
                    </span>

                    <span class="time">
                        ${member.time || "—"}
                    </span>

                </div>

            `;


            container.appendChild(card);

        });


        document.getElementById(
            "present-count"
        ).textContent = present;


        document.getElementById(
            "late-count"
        ).textContent = late;


        document.getElementById(
            "absent-count"
        ).textContent = absent;


        document.getElementById(
            "team-count"
        ).textContent =
            `${team.length} members`;


        document.getElementById(
            "date-display"
        ).textContent =
            formatDate(selectedDate);


        updateAttendanceButton(
            team
        );

    }


    catch (error) {

        console.error(error);

        container.innerHTML = `
            <div class="error">
                Unable to load attendance data.
            </div>
        `;

    }

}


// ------------------------------------------------
// MARK ATTENDANCE
// ------------------------------------------------

async function markAttendance() {

    const button =
        document.getElementById(
            "mark-attendance"
        );


    const message =
        document.getElementById(
            "attendance-message"
        );


    button.disabled = true;

    button.textContent =
        "Marking...";


    try {

        const response =
            await fetch(
                "/api/attendance",
                {
                    method: "POST"
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            showMessage(
                data.error ||
                "Unable to mark attendance.",
                "error"
            );

            return;

        }


        showMessage(
            `${data.status.toUpperCase()} at ${data.time}`,
            "success"
        );


        await loadTeam();

    }


    catch (error) {

        console.error(error);

        showMessage(
            "Unable to connect to the server.",
            "error"
        );

    }


    finally {

        button.disabled = false;

        button.textContent =
            "Mark Attendance";

    }

}


// ------------------------------------------------
// UPDATE BUTTON
// ------------------------------------------------

function updateAttendanceButton(team) {

    const currentUser =
        document.getElementById(
            "user-name"
        ).textContent;


    const today =
        getToday();


    const selectedDate =
        document.getElementById(
            "attendance-date"
        ).value;


    const button =
        document.getElementById(
            "mark-attendance"
        );


    if (selectedDate !== today) {

        button.disabled = true;

        button.textContent =
            "Select today";

        return;

    }


    const member =
        team.find(
            item =>
                item.name === currentUser
        );


    if (
        member &&
        member.status !== "absent"
    ) {

        button.disabled = true;

        button.textContent =
            "Attendance already marked";

        return;

    }


    button.disabled = false;

    button.textContent =
        "Mark Attendance";
}


// ------------------------------------------------
// LOGOUT
// ------------------------------------------------

async function logout() {

    await fetch(
        "/api/logout",
        {
            method: "POST"
        }
    );


    location.reload();
}


// ------------------------------------------------
// EVENTS
// ------------------------------------------------

document
    .getElementById("login-form")
    .addEventListener(
        "submit",
        login
    );


document
    .getElementById("mark-attendance")
    .addEventListener(
        "click",
        markAttendance
    );


document
    .getElementById("attendance-date")
    .addEventListener(
        "change",
        loadTeam
    );


document
    .getElementById("logout")
    .addEventListener(
        "click",
        logout
    );


document
    .getElementById("attendance-date")
    .value = getToday();


loadCurrentUser();
