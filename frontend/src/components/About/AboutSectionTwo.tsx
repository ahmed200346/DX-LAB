import Image from "next/image";

const AboutSectionTwo = () => {
  return (
    <section className="bg-blue-50 py-16 md:py-20 lg:py-28">
      <div className="container">
        <div className="-mx-4 flex flex-wrap items-center">
          <div className="w-full px-4 lg:w-1/2">
            <div
              className="relative mx-auto mb-12 aspect-25/24 max-w-[500px] text-center lg:m-0"
              data-wow-delay=".15s"
            >
              <img
                src="https://assets.website-files.com/604197abb436036ef8167c1a/649070a0967bdf5da028ac39_blog_2022-11_protein%20structure%20prediction%20models%401300w.png"
                alt="Molecular Intelligence"
                className="rounded-xl shadow-lg"
              />
            </div>
          </div>
          <div className="w-full px-4 lg:w-1/2">
            <div className="max-w-[470px]">
              <div className="mb-9">
                <h3 className="mb-4 text-xl font-bold text-black dark:text-white sm:text-2xl lg:text-xl xl:text-2xl">
                  Deep Biological Understanding
                </h3>
                <p className="text-base font-medium leading-relaxed text-body-color sm:text-lg sm:leading-relaxed">
                  We don&apos;t just look for matches; we understand the underlying biological mechanisms. Our system bridges the gap between raw data and medical breakthroughs.
                </p>
              </div>
              <div className="mb-9">
                <h3 className="mb-4 text-xl font-bold text-black dark:text-white sm:text-2xl lg:text-xl xl:text-2xl">
                  Explainable AI (XAI)
                </h3>
                <p className="text-base font-medium leading-relaxed text-body-color sm:text-lg sm:leading-relaxed">
                  Every compound selected by our system comes with a clear scientific rationale, allowing researchers to understand the &quot;why&quot; behind every prediction.
                </p>
              </div>
              <div className="mb-1">
                <h3 className="mb-4 text-xl font-bold text-black dark:text-white sm:text-2xl lg:text-xl xl:text-2xl">
                  High-Throughput Virtual Screening
                </h3>
                <p className="text-base font-medium leading-relaxed text-body-color sm:text-lg sm:leading-relaxed">
                  DEX-LAB orchestrates massive parallel compute cycles to evaluate binding affinities and toxicity profiles at a scale previously impossible.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default AboutSectionTwo;
