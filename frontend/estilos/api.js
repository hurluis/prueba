(() => {
  const normalizeBase = (value) => {
    if (!value) {
      return '';
    }
    return value.endsWith('/') ? value.slice(0, -1) : value;
  };

  const candidateBases = [];
  const metaBase = document.querySelector('meta[name="api-base-url"]');
  if (metaBase?.content) {
    candidateBases.push(normalizeBase(metaBase.content));
  }

  candidateBases.push('/api');
  candidateBases.push('');

  let resolvedBase = null;

  const fetchWithBase = async (base, path, options) => {
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return fetch(`${base}${cleanPath}`, options);
  };

  const tryCandidates = async (path, options) => {
    const basesToTry = resolvedBase !== null
      ? [resolvedBase, ...candidateBases.filter((base) => base !== resolvedBase)]
      : candidateBases;

    let lastError;

    for (const base of basesToTry) {
      try {
        const response = await fetchWithBase(base, path, options);

        if (response.status === 404 && base !== '') {
          // Puede que estemos golpeando la ruta equivocada (por ejemplo /api en local)
          // Continuamos probando con la siguiente opción.
          continue;
        }

        resolvedBase = base;
        return response;
      } catch (error) {
        lastError = error;
      }
    }

    if (lastError) {
      throw lastError;
    }

    return fetchWithBase('', path, options);
  };

  window.apiFetch = async (path, options = {}) => {
    return tryCandidates(path, options);
  };

  Object.defineProperty(window, 'API_BASE_URL', {
    get() {
      return resolvedBase ?? candidateBases[0] ?? '';
    }
  });

  // Modal and Authentication functionality
  document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM Content Loaded - Initializing authentication...');
    
    const loginModal = document.getElementById('login-modal');
    const registerModal = document.getElementById('register-modal');
    const loginLink = document.getElementById('login-link');
    const registerLink = document.getElementById('register-link');
    const myReservationsLink = document.getElementById('my-reservations-link');
    const logoutLink = document.getElementById('logout-link');
    const closeButtons = document.querySelectorAll('.close');

    console.log('Found elements:', {
      loginModal: !!loginModal,
      registerModal: !!registerModal,
      loginLink: !!loginLink,
      registerLink: !!registerLink,
      myReservationsLink: !!myReservationsLink,
      logoutLink: !!logoutLink,
      closeButtons: closeButtons.length
    });

    // Check if user is logged in
    const userId = localStorage.getItem('userId');
    if (userId) {
      loginLink.classList.add('hidden');
      registerLink.classList.add('hidden');
      myReservationsLink.classList.remove('hidden');
      logoutLink.classList.remove('hidden');
    }

    // Function to open modal
    const openModal = (modal) => {
      if (!modal) {
        console.error('Modal element not found');
        return;
      }
      console.log('Opening modal');
      modal.classList.remove('hidden');
      modal.style.display = 'flex';
    };

    // Function to close modal
    const closeModal = (modal) => {
      if (!modal) {
        console.error('Modal element not found');
        return;
      }
      console.log('Closing modal');
      modal.classList.add('hidden');
      modal.style.display = 'none';
    };

    // Event listeners for opening modals
    loginLink?.addEventListener('click', (e) => {
      console.log('Login link clicked');
      e.preventDefault();
      openModal(loginModal);
    });

    registerLink?.addEventListener('click', (e) => {
      console.log('Register link clicked');
      e.preventDefault();
      openModal(registerModal);
    });

    // Event listeners for closing modals
    closeButtons.forEach(button => {
      button.addEventListener('click', () => {
        console.log('Close button clicked');
        closeModal(loginModal);
        closeModal(registerModal);
      });
    });

    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
      if (e.target === loginModal || e.target === registerModal) {
        console.log('Clicked outside modal');
        closeModal(loginModal);
        closeModal(registerModal);
      }
    });

    // Register form submission
    const registerForm = document.getElementById('register-form');
    console.log('Register form found:', !!registerForm);
    
    registerForm?.addEventListener('submit', async (e) => {
      console.log('Register form submitted');
      e.preventDefault();
      const name = document.getElementById('register-name').value;
      const email = document.getElementById('register-email').value;
      const password = document.getElementById('register-password').value;
      const messageElement = document.getElementById('register-message');
      
      console.log('Register form data:', { name, email, hasPassword: !!password });

      try {
        const response = await apiFetch('/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, password })
        });

        const data = await response.json();

        if (response.ok) {
          messageElement.textContent = data.message;
          messageElement.style.color = 'green';
          localStorage.setItem('userId', data.user_id);
          setTimeout(() => window.location.reload(), 1000);
        } else {
          messageElement.textContent = data.message;
          messageElement.style.color = 'red';
        }
      } catch (error) {
        messageElement.textContent = 'Error al registrar usuario';
        messageElement.style.color = 'red';
      }
    });

    // Login form submission
    const loginForm = document.getElementById('login-form');
    console.log('Login form found:', !!loginForm);

    loginForm?.addEventListener('submit', async (e) => {
      console.log('Login form submitted');
      e.preventDefault();
      const email = document.getElementById('login-email').value;
      const password = document.getElementById('login-password').value;
      const messageElement = document.getElementById('login-message');
      
      console.log('Login form data:', { email, hasPassword: !!password });

      try {
        const response = await apiFetch('/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
          messageElement.textContent = data.message;
          messageElement.style.color = 'green';
          localStorage.setItem('userId', data.user_id);
          setTimeout(() => window.location.reload(), 1000);
        } else {
          messageElement.textContent = data.message;
          messageElement.style.color = 'red';
        }
      } catch (error) {
        messageElement.textContent = 'Error al iniciar sesión';
        messageElement.style.color = 'red';
      }
    });

    // Logout functionality
    logoutLink?.addEventListener('click', (e) => {
      e.preventDefault();
      localStorage.removeItem('userId');
      window.location.reload();
    });
  });
})();
