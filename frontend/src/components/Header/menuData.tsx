import { Menu } from "@/types/menu";

const menuData: Menu[] = [
  {
    id: 1,
    title: "Home",
    path: "/",
    newTab: false,
  },
  {
    id: 2,
    title: "About",
    path: "/about",
    newTab: false,
  },
  {
    id: 3,
    title: "Target Discovery",
    path: "/agent",
    newTab: false,
  },
  {
    id: 6,
    title: "Hypothesis Generator",
    path: "/hypothesis-generator",
    newTab: false,
  },
  {
    id: 7,
    title: "MediSafe AI",
    path: "/safety",
    newTab: false,
  },
  {
    id: 8,
    title: "More Agents",
    newTab: false,
    submenu: [
      {
        id: 81,
        title: "Lab Orchestrator",
        path: "/orchestrator",
        newTab: false,
      },
      {
        id: 82,
        title: "Reporter Agent",
        path: "/reporter",
        newTab: false,
      },
      {
        id: 83,
        title: "Data Manager",
        path: "/data-manager",
        newTab: false,
      },
      {
        id: 84,
        title: "Lab Automation",
        path: "/automation",
        newTab: false,
      },
    ]
  },
  {
    id: 4,
    title: "Blog",
    path: "/blog",
    newTab: false,
  },
  {
    id: 5,
    title: "Support",
    path: "/contact",
    newTab: false,
  },
];
export default menuData;
