***Both **node_modules** and **lib** folder of virtualenv present in moviebackend has been deleted.***

# Movie Booking System - README

This project is a Movie Booking System that allows users to browse and book movie tickets for various shows. The system consists of a backend built with Flask, a frontend developed using Vue.js, and Celery for background task processing.

## Getting Started

1. **Setting Up the Backend:**

   Navigate to the backend directory:
   ```
   cd Ticket_show/movie-booker/
   ```

   Activate the virtual environment:
   ```
   source backend/moviebackend/bin/activate
   ```

   Start the Flask backend by running the `app.py` file. You can do this using Visual Studio Code by pressing F5 and providing the path to the `app.py` file. Alternatively, run:
   ```
   python3 backend/moviebackend/app.py
 
   ```

2. **Starting the Frontend:**

   From the root directory (`Ticket_show/movie-booker`), open a terminal and run:
   ```
   npm run dev
   ```

   This will start the frontend server and make the application accessible at `http://localhost:5173`.

3. **Running Celery for Background Tasks:**

   In a new terminal, navigate to the backend directory:
   ```
   cd Ticket_show/movie-booker/backend/moviebackend
   ```

   Start the Celery worker and beat scheduler:
   ```
   celery -A app:celeryapp worker --beat --loglevel=info
   ```

## How the System Works

1. **Backend:**

   The backend is powered by Flask and manages various functionalities such as user registration, authentication, venue and show management, ticket booking, and cancellation. It also utilizes Celery to handle background tasks, including sending emails to inactive users and generating reports. The backend API endpoints are defined in `app.py`.

2. **Frontend:**

   The frontend, built with Vue.js, provides a user-friendly interface for browsing shows, booking tickets, and managing user accounts. Vue components in the `src/components` directory handle different aspects of the user interface.

3. **Celery:**

   Celery is used for asynchronous task processing. It enables the scheduling of daily and monthly jobs, such as sending emails to inactive users and generating reports. The Celery configuration is integrated within `app.py`.

## Running the Applications

1. Start the backend as described above, ensuring the virtual environment is activated.
2. Start the frontend by running `npm run dev` in the root directory.
3. Launch Celery by running the Celery worker and beat scheduler command.

With these steps completed, you'll have the Movie Booking System up and running. Access the frontend at `http://localhost:5173` to explore the application, book tickets, and manage your account.

Please make sure to customize the configuration settings, email credentials, and other parameters as needed before deploying the project to a production environment.

**Note:** This guide assumes you have the necessary software dependencies installed, including Python, Node.js, Flask, Vue.js, and Celery. If you encounter any issues, refer to the project documentation or consult the relevant documentation for each technology.



***Both **node_modules** and **lib** folder of virtualenv has been deleted.***