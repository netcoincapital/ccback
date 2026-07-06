const io = require('socket.io-client');

const socket = io('http://localhost:5000', {
  auth: {
    user_id: 'YOUR_USER_ID'
  },
  transports: ['websocket', 'polling']
});

socket.on('connect', () => {
  console.log('Connected to WebSocket server');
});

socket.on('disconnect', () => {
  console.log('Disconnected from WebSocket server');
});

socket.on('error', (data) => {
  console.error('WebSocket error:', data.message);
});

socket.on('joined_conversation', (data) => {
  console.log('Joined conversation:', data.conversation_id);
});

socket.on('left_conversation', (data) => {
  console.log('Left conversation:', data.conversation_id);
});

socket.on('new_message', (data) => {
  console.log('New message received:', data);
  displayMessage(data);
});

socket.on('message_edited', (data) => {
  console.log('Message edited:', data);
  updateMessage(data);
});

socket.on('message_deleted', (data) => {
  console.log('Message deleted:', data.message_id);
  removeMessage(data.message_id);
});

socket.on('user_typing', (data) => {
  console.log('User typing:', data);
  if (data.is_typing) {
    showTypingIndicator(data.user_id);
  } else {
    hideTypingIndicator(data.user_id);
  }
});

function joinConversation(conversationId, userId) {
  socket.emit('join_conversation', {
    user_id: userId,
    conversation_id: conversationId
  });
}

function leaveConversation(conversationId, userId) {
  socket.emit('leave_conversation', {
    user_id: userId,
    conversation_id: conversationId
  });
}

function sendMessage(senderId, receiverId, message, messageType = 'text') {
  socket.emit('send_message', {
    sender_id: senderId,
    receiver_id: receiverId,
    message: message,
    message_type: messageType
  });
}

function startTyping(conversationId, userId) {
  socket.emit('typing_start', {
    user_id: userId,
    conversation_id: conversationId
  });
}

function stopTyping(conversationId, userId) {
  socket.emit('typing_stop', {
    user_id: userId,
    conversation_id: conversationId
  });
}

function editMessage(messageId, userId, newMessage) {
  socket.emit('edit_message', {
    user_id: userId,
    message_id: messageId,
    message: newMessage
  });
}

function deleteMessage(messageId, userId) {
  socket.emit('delete_message', {
    user_id: userId,
    message_id: messageId
  });
}

let typingTimeout;
const conversationId = 'CONVERSATION_ID';
const userId = 'YOUR_USER_ID';

joinConversation(conversationId, userId);

const messageInput = document.getElementById('message-input');
messageInput.addEventListener('input', () => {
  startTyping(conversationId, userId);
  
  clearTimeout(typingTimeout);
  typingTimeout = setTimeout(() => {
    stopTyping(conversationId, userId);
  }, 1000);
});

const sendButton = document.getElementById('send-button');
sendButton.addEventListener('click', () => {
  const message = messageInput.value;
  if (message.trim()) {
    sendMessage(userId, 'RECEIVER_ID', message);
    messageInput.value = '';
    stopTyping(conversationId, userId);
  }
});

function displayMessage(messageData) {
  const messageDiv = document.createElement('div');
  messageDiv.id = `message-${messageData.message_id}`;
  messageDiv.className = 'message';
  
  let messageText = messageData.message;
  if (messageData.is_edited) {
    messageText += ' <span class="edited-tag">(edited)</span>';
  }
  
  messageDiv.innerHTML = `
    <div class="message-content">${messageText}</div>
    <div class="message-time">${new Date(messageData.created_at).toLocaleTimeString()}</div>
  `;
  
  document.getElementById('messages-container').appendChild(messageDiv);
}

function updateMessage(messageData) {
  const messageDiv = document.getElementById(`message-${messageData.message_id}`);
  if (messageDiv) {
    let messageText = messageData.message;
    if (messageData.is_edited) {
      messageText += ' <span class="edited-tag">(edited)</span>';
    }
    messageDiv.querySelector('.message-content').innerHTML = messageText;
  }
}

function removeMessage(messageId) {
  const messageDiv = document.getElementById(`message-${messageId}`);
  if (messageDiv) {
    messageDiv.remove();
  }
}

function showTypingIndicator(userId) {
  const typingDiv = document.getElementById('typing-indicator');
  if (typingDiv) {
    typingDiv.style.display = 'block';
    typingDiv.textContent = 'User is typing...';
  }
}

function hideTypingIndicator(userId) {
  const typingDiv = document.getElementById('typing-indicator');
  if (typingDiv) {
    typingDiv.style.display = 'none';
  }
}

module.exports = {
  socket,
  joinConversation,
  leaveConversation,
  sendMessage,
  startTyping,
  stopTyping,
  editMessage,
  deleteMessage
};

