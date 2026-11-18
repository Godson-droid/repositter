import { Nav } from './components/Nav'
import { Hero } from './components/Hero'
import { Stats } from './components/Stats'
import { Triage } from './components/Triage'
import { Runs } from './components/Runs'
import { Gate } from './components/Gate'
import { Memory } from './components/Memory'
import { Findings } from './components/Findings'
import { Blocks } from './components/Blocks'
import { Footer } from './components/Footer'

export default function App() {
  return (
    <div className="min-h-screen bg-night-950">
      <Nav />
      <main>
        <Hero />
        <Stats />
        <Triage />
        <Runs />
        <Gate />
        <Memory />
        <Findings />
        <Blocks />
      </main>
      <Footer />
    </div>
  )
}
