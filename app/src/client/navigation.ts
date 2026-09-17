import {
  Activity,
  Bot,
  CirclePlay,
  ClipboardCheck,
  FileCode,
  FlaskConical,
  Gauge,
  Info,
  ListTree,
  type LucideIcon,
  Plug,
  Rocket,
  ShieldCheck,
  Split,
  Target,
  TriangleAlert,
  Waypoints,
  Wind,
  Workflow,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const navigation: NavGroup[] = [
  {
    title: "Overview",
    items: [
      { label: "Merge Safety", href: "/merge-safety", icon: ShieldCheck },
      { label: "Coverage", href: "/", icon: Gauge },
      { label: "High Risk", href: "/high-risk", icon: TriangleAlert },
    ],
  },
  {
    title: "Specs",
    items: [
      { label: "Requirements", href: "/specs", icon: ListTree },
      { label: "Conflicts", href: "/conflicts", icon: Split },
    ],
  },
  {
    title: "Results",
    items: [
      { label: "Validation Runs", href: "/runs", icon: CirclePlay },
      { label: "Test Runs", href: "/test-runs", icon: FlaskConical },
      { label: "Vendor Coverage", href: "/vendor-coverage", icon: Plug },
    ],
  },
  {
    title: "Analysis",
    items: [
      { label: "Impact", href: "/impact", icon: Waypoints },
      { label: "Drift", href: "/drift", icon: Wind },
    ],
  },
  {
    title: "Compliance",
    items: [
      { label: "Corpus Reviews", href: "/corpus/reviews", icon: ClipboardCheck },
      { label: "SLO Status", href: "/slo-status", icon: Target },
    ],
  },
  {
    title: "Automation",
    items: [
      { label: "Agent Tasks", href: "/tasks", icon: Bot },
      { label: "Factory Report", href: "/factory", icon: Activity },
      { label: "Flows", href: "/flows", icon: Workflow },
    ],
  },
  {
    title: "Docs",
    items: [
      { label: "Getting Started", href: "/getting-started", icon: Rocket },
      { label: "Spec Syntax", href: "/spec-syntax", icon: FileCode },
      { label: "About", href: "/about", icon: Info },
    ],
  },
];
