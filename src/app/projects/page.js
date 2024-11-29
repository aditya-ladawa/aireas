'use client';
import { useState } from 'react';

export default function Projects() {
  // Mock state for projects
  const [projects, setProjects] = useState([]);

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-gray-900 via-gray-800 to-black">
      {/* Page Title */}
      <h1 className="text-4xl font-light text-transparent bg-clip-text bg-gradient-to-r from-white to-cyan-300 py-6 text-center">
        Projects
      </h1>

      {/* First Row: Form Section */}
      <div className="h-[30%] flex items-center justify-center px-6">
        <div className="w-full max-w-4xl bg-gray-800 p-6 rounded-lg shadow-lg hover:shadow-xl transition duration-300">
          <h2 className="text-2xl text-white mb-6 text-center">Add a New Project</h2>
          <form className="flex items-center space-x-4">
            <input
              type="text"
              placeholder="Project Name"
              className="flex-grow p-3 bg-gray-700 text-white rounded-lg shadow-md focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <input
              type="text"
              placeholder="Description"
              className="flex-grow p-3 bg-gray-700 text-white rounded-lg shadow-md focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <button
              type="button"
              className="px-6 py-3 bg-gradient-to-r from-cyan-500 to-teal-400 text-black font-medium rounded-lg shadow-lg hover:shadow-xl transition duration-300"
            >
              Submit
            </button>
          </form>
        </div>
      </div>

      {/* Second Row: Projects Section */}
      <div className="h-[70%] overflow-y-auto px-6 py-8">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl text-white mb-6 text-center">Your Projects</h2>

          {projects.length === 0 ? (
            <p className="text-center text-gray-400">No projects</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {projects.map((project, index) => (
                <div
                  key={index}
                  className="bg-gray-800 p-6 rounded-lg shadow-lg hover:shadow-xl transition duration-300 flex flex-col justify-between"
                >
                  <div>
                    <h3 className="text-xl font-semibold text-white">{project.name}</h3>
                    <p className="text-gray-300 mt-2">{project.description}</p>
                  </div>
                  <div className="mt-4">
                    <button
                      type="button"
                      className="w-full px-4 py-2 text-sm font-medium text-black bg-gradient-to-r from-cyan-500 to-teal-400 rounded-lg shadow hover:shadow-xl transition duration-300"
                    >
                      View
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
