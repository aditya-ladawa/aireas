// src/app/page.js or a similar path where your Page component is located

export default function Page() {
  return (
      <div className="flex h-screen">
          {/* First Column: 20% Width */}
          <div className="w-1/5 p-4 border-r-2 border-gray-600 flex flex-col justify-between">
              <button className="w-full bg-blue-500 text-white font-semibold py-2 rounded-lg hover:bg-blue-600 transition duration-300">
                  Upload PDF
              </button>
          </div>

          {/* Second Column: 50% Width */}
          <div className="w-1/2 p-4 border-r-2 border-gray-600 flex flex-col justify-between">
              <h2 className="text-xl font-bold mb-4">Main Content Area</h2>
              <p>This area is for displaying the main content of the dashboard.</p>
          </div>

          {/* Third Column: 30% Width */}
          <div className="w-1/3 p-4 flex flex-col justify-between">
              <h2 className="text-xl font-bold mb-4">Side Information</h2>
              <p>This area can be used for additional information, links, or other relevant details.</p>
          </div>
      </div>
  );
}
