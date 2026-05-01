import { Blog } from "@/types/blog";

const blogData: Blog[] = [
  {
    id: 1,
    title: "Accelerating Drug Discovery with Multi-Agent AI",
    paragraph:
      "Discover how specialized AI agents collaborate to evaluate millions of compounds, drastically reducing the time required for virtual screening.",
    image: "https://tse4.mm.bing.net/th/id/OIP.BopP_7cDXQMWknZzREUYVgHaD4?rs=1&pid=ImgDetMain&o=7&rm=3",
    author: {
      name: "Dr. Sarah Chen",
      image: "/images/blog/author-03.png",
      designation: "Lead AI Researcher",
    },
    tags: ["AI"],
    publishDate: "2025",
  },
  {
    id: 2,
    title: "The Role of Protein Structure Prediction in Modern Medicine",
    paragraph:
      "An in-depth look at how AlphaFold integration allows our agents to identify promising target proteins with unprecedented accuracy.",
    image: "https://assets.website-files.com/604197abb436036ef8167c1a/649070a0967bdf5da028ac39_blog_2022-11_protein%20structure%20prediction%20models%401300w.png",
    author: {
      name: "James Peterson",
      image: "/images/blog/author-02.png",
      designation: "Bioinformatics Specialist",
    },
    tags: ["Research"],
    publishDate: "2025",
  },
  {
    id: 3,
    title: "Overcoming Data Bottlenecks in Molecular Databases",
    paragraph:
      "Learn how the Data Manager Agent efficiently parses and indexes large-scale datasets from PubChem and ChEMBL for real-time querying.",
    image: "https://tse1.mm.bing.net/th/id/OIP.F4icetXvE7AILPZC-gEI4AHaEM?rs=1&pid=ImgDetMain&o=7&rm=3",
    author: {
      name: "Dr. Elena Rostova",
      image: "/images/blog/author-03.png",
      designation: "Data Scientist",
    },
    tags: ["Cheminformatics"],
    publishDate: "2025",
  },
];
export default blogData;
