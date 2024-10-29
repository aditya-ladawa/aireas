// app/layout.js or a similar path where your Layout component is located

import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';

export const metadata = {
  title: 'Dashboard',
  description: 'Dashboard Layout',
}

export default function Layout({ children }) {
  return (
      <div className="flex-1 flex flex-col">
        <Navbar />
        <main className="p-8">
          {children}
        </main>
      </div>
  );
}
