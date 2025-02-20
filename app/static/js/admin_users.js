let currentUserId = null;
let modal = null;

document.addEventListener('DOMContentLoaded', function() {
    modal = new bootstrap.Modal(document.getElementById('addPointsModal'));
});

function showAddPointsModal(userId, username) {
    currentUserId = userId;
    document.getElementById('modalUsername').textContent = username;
    document.getElementById('pointAmount').value = '';
    document.getElementById('pointReason').value = '';
    modal.show();
}

async function addPoints() {
    const amount = document.getElementById('pointAmount').value;
    const reason = document.getElementById('pointReason').value;
    
    try {
        const response = await fetch(`/admin/users/${currentUserId}/update-points`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify({
                points: parseInt(amount),
                reason: reason
            })
        });
        
        const data = await response.json();
        if (data.success) {
            location.reload();
        } else {
            alert(data.message || 'エラーが発生しました。');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('エラーが発生しました。');
    }
} 