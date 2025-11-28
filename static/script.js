// inside your existing submit event listener:
document.getElementById('bookingForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const fullName = document.getElementById('fullName').value.trim();
    const email = document.getElementById('email').value.trim();

    if (!fullName || !email) {
        return alert('Please enter your name and email.');
    }

    try {
        const res = await fetch('/book', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_name: fullName,
                course_id: parseInt(courseId),
                email: email
            })
        });

        if (!res.ok) {
            const err = await res.json();
            alert('Error: ' + (err.detail || 'Unknown error'));
            return;
        }

        alert('✓ Booked successfully! A confirmation email has been sent to ' + email);
        document.getElementById('bookingForm').reset();
        loadCourseStats();
    } catch (e) {
        alert('Booking failed. Please try again.');
        console.error(e);
    }
});
