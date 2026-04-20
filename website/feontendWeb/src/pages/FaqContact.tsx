import { Link } from "react-router-dom";
import { Download, Mail, BookOpen, FileText, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHero } from "@/components/PageHero";
import { SectionShell, SectionHeader } from "@/components/SectionShell";
import { motion } from "framer-motion";
import { useState } from "react";

const faqs = [
  { q: "What is SecureScan Studio?", a: "SecureScan Studio is a desktop application for code security scanning, vulnerability analysis, and guided remediation. It helps developers and security teams find issues, generate fixes, review patches, and track their security work in one focused workspace." },
  { q: "Who is SecureScan Studio designed for?", a: "It's built for security engineers, engineering leads, CTOs, and developers responsible for code quality and secure releases. Anyone who needs a structured way to scan, fix, and review security issues will find it valuable." },
  { q: "How does code scanning work?", a: "SecureScan Studio performs context-aware analysis of your source code. It identifies vulnerabilities, classifies them by severity, and provides file-level detail — going beyond simple pattern matching to surface real security risks." },
  { q: "How are fix suggestions generated?", a: "For each finding, SecureScan Studio generates a code-level fix suggestion that addresses the vulnerability. You see the proposed change, the rationale behind it, and the security improvement — all before applying anything." },
  { q: "What is patch review?", a: "Patch review lets you inspect generated fixes in a clean diff view before accepting them. You can review every line change, understand the modification, and decide whether to apply, adjust, or skip the fix." },
  { q: "How are sessions saved and revisited?", a: "Every scan creates a session that captures your findings, fixes, and review progress. You can save sessions, come back to them later, and maintain a complete history of your security work across projects." },
  { q: "What does Aegix do?", a: "Aegix is a guided remediation assistant that walks you through complex vulnerabilities step by step. It explains the issue, recommends the approach, and helps you implement the fix with confidence." },
  { q: "How can our team get started?", a: "Download SecureScan Studio from the download page, open your project, and run your first scan. The application guides you through the workflow from there. Team plans are available for organizations that need shared access." },
  { q: "Is my code sent to external servers?", a: "SecureScan Studio is designed as a desktop-first application with a focus on privacy. Scan processing and analysis happen within your workspace environment." },
  { q: "What languages and frameworks are supported?", a: "SecureScan Studio supports a wide range of popular programming languages and frameworks. Coverage is continuously expanding with each release." },
];

export default function FaqContact() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [formState, setFormState] = useState({ name: "", email: "", message: "" });

  return (
    <>
      <PageHero
        overline="FAQ & Contact"
        title={
          <>
            Questions? We have <span className="serif-accent">answers</span>.
          </>
        }
        subtitle="Find answers to common questions about SecureScan Studio, or reach out to our team for support."
      />

      {/* FAQ */}
      <SectionShell dotted>
        <SectionHeader overline="FAQ" title="Frequently asked questions" center />
        <div className="max-w-2xl mx-auto space-y-3">
          {faqs.map((faq, i) => (
            <motion.div
              key={faq.q}
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.03 }}
              className="rounded-xl border border-border-soft bg-card overflow-hidden"
            >
              <button
                onClick={() => setOpenIndex(openIndex === i ? null : i)}
                className="w-full flex items-center justify-between p-5 text-left"
              >
                <span className="font-semibold text-foreground text-sm pr-4">{faq.q}</span>
                <span className="text-text-tertiary shrink-0 text-lg">{openIndex === i ? "−" : "+"}</span>
              </button>
              {openIndex === i && (
                <div className="px-5 pb-5 pt-0">
                  <p className="text-sm text-text-secondary leading-relaxed">{faq.a}</p>
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </SectionShell>

      {/* Contact */}
      <SectionShell>
        <SectionHeader overline="Contact" title="Get in touch" center />
        <div className="grid md:grid-cols-2 gap-10 max-w-4xl mx-auto">
          {/* Contact Form */}
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="p-6 rounded-xl border border-border-soft bg-card"
          >
            <h3 className="font-semibold text-foreground mb-4">Send us a message</h3>
            <form onSubmit={(e) => e.preventDefault()} className="space-y-4">
              <div>
                <label className="text-xs font-medium text-text-secondary mb-1 block">Name</label>
                <input
                  type="text"
                  value={formState.name}
                  onChange={(e) => setFormState({ ...formState, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-border-soft bg-surface text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                  placeholder="Your name"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-text-secondary mb-1 block">Email</label>
                <input
                  type="email"
                  value={formState.email}
                  onChange={(e) => setFormState({ ...formState, email: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-border-soft bg-surface text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                  placeholder="you@company.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-text-secondary mb-1 block">Message</label>
                <textarea
                  value={formState.message}
                  onChange={(e) => setFormState({ ...formState, message: e.target.value })}
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg border border-border-soft bg-surface text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none"
                  placeholder="How can we help?"
                />
              </div>
              <Button className="w-full">Send Message</Button>
            </form>
          </motion.div>

          {/* Support Cards */}
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="space-y-4"
          >
            {[
              { icon: Mail, title: "Email Support", desc: "Reach our team directly for technical questions or account inquiries.", action: "support@securescan.studio" },
              { icon: BookOpen, title: "Documentation", desc: "Browse comprehensive guides, tutorials, and API references.", action: "View Docs" },
              { icon: FileText, title: "Release Notes", desc: "Stay updated with the latest features, improvements, and fixes.", action: "View Changelog" },
            ].map((card) => (
              <div key={card.title} className="p-5 rounded-xl border border-border-soft bg-card hover:border-border transition-colors">
                <div className="flex items-start gap-4">
                  <card.icon className="w-5 h-5 text-text-secondary mt-0.5 shrink-0" />
                  <div>
                    <h4 className="font-semibold text-foreground text-sm mb-1">{card.title}</h4>
                    <p className="text-xs text-text-secondary leading-relaxed mb-2">{card.desc}</p>
                    <span className="text-xs font-medium text-accent">{card.action}</span>
                  </div>
                </div>
              </div>
            ))}
          </motion.div>
        </div>
      </SectionShell>

      {/* CTA */}
      <SectionShell dark dotted className="!py-24">
        <div className="text-center max-w-2xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl md:text-4xl font-bold text-dark-text mb-4">
              Ready to get started?
            </h2>
            <p className="text-dark-muted text-lg mb-8">
              Download SecureScan Studio and experience a better way to handle code security.
            </p>
            <Link to="/download">
              <Button size="lg" variant="secondary" className="gap-2">
                <Download className="w-4 h-4" />
                Download
              </Button>
            </Link>
          </motion.div>
        </div>
      </SectionShell>
    </>
  );
}
