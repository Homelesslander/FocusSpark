// Celebration Effects for Task Completion

// Task completion messages by importance
const COMPLETION_MESSAGES = {
  Major: [
    "Amazing! 🌟",
    "MISSION ACCOMPLISHED! 🎉",
    "Incredible Work!",
    "YOU'RE A CHAMPION! 👑",
    "PHENOMENAL EFFORT! ✨"
  ],
  Medium: [
    "Nailed it! ✨",
    "Another one checked off - you're on fire! 🔥",
    "Consistent progress adds up!",
    "Great job! 💪",
    "Keep it up! 🚀"
  ],
  Minor: [
    "Done! ✅",
    "Small win, big momentum!",
    "Every task counts!",
    "Nice work! 👍",
    "Building your streak! 💯"
  ]
};

// Get random message for importance level
function getRandomMessage(importance) {
  const messages = COMPLETION_MESSAGES[importance] || COMPLETION_MESSAGES.Minor;
  return messages[Math.floor(Math.random() * messages.length)];
}

// Create confetti effect for Major tasks
function createConfetti() {
  const canvas = document.createElement('canvas');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  canvas.style.position = 'fixed';
  canvas.style.top = '0';
  canvas.style.left = '0';
  canvas.style.pointerEvents = 'none';
  canvas.style.zIndex = '9999';
  document.body.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  const confetti = [];

  // Create confetti pieces
  for (let i = 0; i < 100; i++) {
    confetti.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height - canvas.height,
      size: Math.random() * 8 + 4,
      speedX: Math.random() * 4 - 2,
      // slower vertical speed so confetti lingers longer on-screen
      speedY: Math.random() * 3 + 3,
      color: `hsl(${Math.random() * 360}, 100%, 50%)`,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: Math.random() * 0.2 - 0.1
    });
  }

  // Animate confetti
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    for (let i = confetti.length - 1; i >= 0; i--) {
      const p = confetti[i];
      
      p.y += p.speedY;
      p.x += p.speedX;
      // gentler gravity so pieces fall more slowly and remain visible
      p.speedY += 0.05;
      p.rotation += p.rotationSpeed;

      if (p.y > canvas.height) {
        confetti.splice(i, 1);
        continue;
      }

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
      ctx.restore();
    }

    if (confetti.length > 0) {
      requestAnimationFrame(animate);
    } else {
      document.body.removeChild(canvas);
    }
  }

  animate();
}

// Create sparkle effect for Minor tasks
function createSparkles(x, y) {
  const sparkles = [];
  for (let i = 0; i < 25; i++) {
    const sparkle = document.createElement('div');
    sparkle.className = 'sparkle';
    sparkle.style.left = x + 'px';
    sparkle.style.top = y + 'px';
    document.body.appendChild(sparkle);

    const angle = (Math.PI * 2 * i) / 15;
    const velocity = 3 + Math.random() * 3;
    let vx = Math.cos(angle) * velocity;
    let vy = Math.sin(angle) * velocity;
    let life = 1;

    const animate = () => {
      // slower decay so sparkles remain longer
      life -= 0.01;
      sparkle.style.opacity = life;
      sparkle.style.transform = `translate(${vx}px, ${vy}px) scale(${life})`;
      
      vx *= 0.98;
      vy *= 0.98;

      if (life > 0) {
        requestAnimationFrame(animate);
      } else {
        document.body.removeChild(sparkle);
      }
    };
    
    animate();
  }
}

// Create color burst effect for Medium tasks
function createColorBurst(element) {
  const burst = document.createElement('div');
  burst.className = 'color-burst';
  burst.style.position = 'absolute';
  burst.style.left = element.offsetLeft + 'px';
  burst.style.top = element.offsetTop + 'px';
  burst.style.width = element.offsetWidth + 'px';
  burst.style.height = element.offsetHeight + 'px';
  document.body.appendChild(burst);

  // keep burst visible a bit longer
  setTimeout(() => {
    document.body.removeChild(burst);
  }, 2000);
}

// Show achievement notification
function showAchievementNotification(message, importance) {
  const notification = document.createElement('div');
  notification.className = `achievement-notification achievement-${importance.toLowerCase()}`;
  notification.textContent = message;
  document.body.appendChild(notification);

  // Display durations per importance level (ms) - extended for better visibility
  const DISPLAY_DURATIONS = {
    Major: 8000,    // Increased from 5000 to 8000ms (8 seconds)
    Medium: 6000,   // Increased from 5000 to 6000ms (6 seconds)  
    Minor: 4000    // Increased from 5000 to 4000ms (4 seconds)
  };
  const fadeDuration = 1000; // Increased fade-out time from 700ms to 1000ms
  const displayFor = DISPLAY_DURATIONS[importance] || 4000;

  setTimeout(() => {
    notification.classList.add('fade-out');
    setTimeout(() => {
      if (notification.parentElement) document.body.removeChild(notification);
    }, fadeDuration);
  }, displayFor);
}

// Play sound effect
function playCompletionSound(importance) {
  // Create a simple beep using Web Audio API
  const audioContext = new (window.AudioContext || window.webkitAudioContext)();
  const oscillator = audioContext.createOscillator();
  const gainNode = audioContext.createGain();

  oscillator.connect(gainNode);
  gainNode.connect(audioContext.destination);

  if (importance === 'Major') {
    // Success chime for major tasks - three ascending notes
    oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime); // C5
    oscillator.frequency.setValueAtTime(659.25, audioContext.currentTime + 0.1); // E5
    oscillator.frequency.setValueAtTime(783.99, audioContext.currentTime + 0.2); // G5
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.6);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.6);
  } else if (importance === 'Medium') {
    // Upbeat ting for medium tasks
    oscillator.frequency.setValueAtTime(880, audioContext.currentTime); // A5
    gainNode.gain.setValueAtTime(0.2, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.3);
  } else {
    // Quick beep for minor tasks
    oscillator.frequency.setValueAtTime(600, audioContext.currentTime);
    gainNode.gain.setValueAtTime(0.15, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.2);
  }
}

// Main celebration function
function celebrateTaskCompletion(importance) {
  const message = getRandomMessage(importance);
  
  // Play sound
  playCompletionSound(importance);

  if (importance === 'Major') {
    // Full celebration for major tasks
    createConfetti();
    showAchievementNotification(message, importance);
  } else if (importance === 'Medium') {
    // Color burst for medium tasks
    const centerX = window.innerWidth / 2;
    const centerY = window.innerHeight / 2;
    createSparkles(centerX, centerY);
    showAchievementNotification(message, importance);
  } else {
    // Quick sparkle for minor tasks
    const centerX = window.innerWidth / 2;
    const centerY = window.innerHeight / 2;
    createSparkles(centerX, centerY);
    showAchievementNotification(message, importance);
  }
}
