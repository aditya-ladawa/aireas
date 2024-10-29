"use client";

export default function Navbar() {
  return (
    <nav className="bg-gray-800 p-4 rounded-b-lg shadow-md">
      <div className="flex items-center justify-between">
        <div className="text-white font-bold text-lg">Research Assistant</div>
        <div className="flex space-x-4">
          <button
            className="text-gray-300 hover:text-white transition duration-300 ease-in-out rounded-lg px-3 py-2 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
            aria-label="Notifications"
          >
            Notifications
          </button>
          <button
            className="text-gray-300 hover:text-white transition duration-300 ease-in-out rounded-lg px-3 py-2 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
            aria-label="Profile"
          >
            Profile
          </button>
        </div>
      </div>
    </nav>
  );
}
