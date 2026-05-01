import AboutSectionOne from "@/components/About/AboutSectionOne";
import AboutSectionTwo from "@/components/About/AboutSectionTwo";
import Breadcrumb from "@/components/Common/Breadcrumb";

import { Metadata } from "next";

export const metadata: Metadata = {
  title: "About DEX-LAB | AI-Powered Virtual Laboratory",
  description: "DEX-LAB is a state-of-the-art virtual laboratory designed to accelerate drug discovery through a collaborative multi-agent AI system.",
};

const AboutPage = () => {
  return (
    <>
      <Breadcrumb
        pageName="Engineering a New Era in Medicine"
        description="DEX-LAB was founded with a singular purpose: to bridge the gap between massive chemical data and life-saving treatments. We are building the infrastructure for the next generation of biopharma."
      />
      <AboutSectionOne />
      <AboutSectionTwo />
    </>
  );
};

export default AboutPage;
